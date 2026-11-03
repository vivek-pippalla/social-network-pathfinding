"""Checksum-verified, additive ingestion of the SNAP ego-Facebook edge list."""

import gzip
import hashlib
import os
import re
import tempfile
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from neo4j import Driver

from app.db.schema import ensure_schema
from app.repositories import ingestion_repo
from app.services.cache_service import CacheService

DATASET_URL = "https://snap.stanford.edu/data/facebook_combined.txt.gz"
DATASET_SHA256 = "125e84db872eeba443d270c70315c256b0af43a502fcfe51f50621166ad035d7"
EXPECTED_DATASET_COUNTS = (4039, 88234)
DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "facebook_combined.txt.gz"
)
USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class DatasetError(ValueError):
    """Raised when a dataset cannot be trusted or loaded consistently."""


@dataclass(frozen=True)
class ParseStats:
    total_lines: int
    valid_edges: int
    malformed: int
    self_loops: int
    duplicates: int
    ignored: int
    unique_users: int

    @property
    def rejected(self) -> int:
        return self.malformed + self.self_loops + self.duplicates

    def as_dict(self) -> dict[str, int]:
        return {
            "total_lines": self.total_lines,
            "valid_edges": self.valid_edges,
            "malformed": self.malformed,
            "self_loops": self.self_loops,
            "duplicates": self.duplicates,
            "ignored": self.ignored,
            "unique_users": self.unique_users,
            "rejected": self.rejected,
        }


@dataclass(frozen=True)
class ParsedDataset:
    user_ids: tuple[str, ...]
    edges: tuple[tuple[str, str], ...]
    stats: ParseStats


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_dataset(path: str | Path, expected_sha256: str = DATASET_SHA256) -> None:
    actual = sha256_file(path)
    if actual.lower() != expected_sha256.lower():
        raise DatasetError("Dataset SHA-256 does not match the expected SNAP file.")


def ensure_dataset_file(
    path: str | Path = DEFAULT_DATASET_PATH,
    *,
    url: str = DATASET_URL,
    expected_sha256: str = DATASET_SHA256,
) -> Path:
    """Use a verified local cache or download to a temporary file atomically."""
    target = Path(path)
    if target.exists():
        verify_dataset(target, expected_sha256)
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".download", dir=target.parent
    )
    os.close(descriptor)
    try:
        urllib.request.urlretrieve(url, temporary_path)
        verify_dataset(temporary_path, expected_sha256)
        os.replace(temporary_path, target)
    except Exception:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass
        raise
    return target


def parse_edge_file(path: str | Path) -> ParsedDataset:
    """Parse an edge list, rejecting malformed, self-loop and duplicate rows."""
    source_path = Path(path)
    open_source = gzip.open if source_path.suffix.lower() == ".gz" else open
    users: set[str] = set()
    edges: set[tuple[str, str]] = set()
    counts: Counter[str] = Counter()
    total_lines = 0

    with open_source(
        source_path, "rt", encoding="utf-8", errors="replace", newline=None
    ) as source:
        for line in source:
            total_lines += 1
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                counts["ignored"] += 1
                continue

            parts = stripped.split()
            if (
                len(parts) != 2
                or not USER_ID_PATTERN.fullmatch(parts[0])
                or not USER_ID_PATTERN.fullmatch(parts[1])
            ):
                counts["malformed"] += 1
                continue

            left, right = parts
            if left == right:
                counts["self_loops"] += 1
                continue

            pair = tuple(sorted((left, right)))
            if pair in edges:
                counts["duplicates"] += 1
                continue

            edges.add(pair)
            users.update(pair)

    ordered_edges = tuple(sorted(edges))
    stats = ParseStats(
        total_lines=total_lines,
        valid_edges=len(ordered_edges),
        malformed=counts["malformed"],
        self_loops=counts["self_loops"],
        duplicates=counts["duplicates"],
        ignored=counts["ignored"],
        unique_users=len(users),
    )
    return ParsedDataset(tuple(sorted(users)), ordered_edges, stats)


def run_ingestion(
    driver: Driver,
    cache: CacheService,
    dataset_path: str | Path,
    *,
    batch_size: int = 2000,
    reset: bool = False,
    wipe_all: bool = False,
    expected_sha256: str = DATASET_SHA256,
    expected_counts: tuple[int, int] | None = EXPECTED_DATASET_COUNTS,
) -> dict:
    """Validate first, then ensure schema and apply bounded, idempotent writes."""
    if (
        isinstance(batch_size, bool)
        or not isinstance(batch_size, int)
        or batch_size < 1
    ):
        raise ValueError("batch_size must be a positive integer")
    if wipe_all and not reset:
        raise ValueError("wipe_all requires reset")

    verify_dataset(dataset_path, expected_sha256)
    parsed = parse_edge_file(dataset_path)
    if not parsed.user_ids or not parsed.edges:
        raise DatasetError("Dataset contains no valid edges.")

    ensure_schema(driver)
    changed = False
    created_users = 0
    created_relationships = 0
    deleted_users = 0
    deleted_relationships = 0
    try:
        if reset:
            if wipe_all:
                deleted_users, deleted_relationships = ingestion_repo.delete_all_data(
                    driver
                )
            else:
                deleted_users, deleted_relationships = ingestion_repo.delete_snap_data(
                    driver
                )
            changed = deleted_users > 0 or deleted_relationships > 0

        for start in range(0, len(parsed.user_ids), batch_size):
            batch_created = ingestion_repo.merge_snap_users(
                driver, list(parsed.user_ids[start : start + batch_size])
            )
            created_users += batch_created
            changed = changed or batch_created > 0

        for start in range(0, len(parsed.edges), batch_size):
            batch_created = ingestion_repo.merge_snap_edges(
                driver, list(parsed.edges[start : start + batch_size])
            )
            created_relationships += batch_created
            changed = changed or batch_created > 0

        actual_counts = ingestion_repo.snap_graph_counts(driver)
        if expected_counts is not None and actual_counts != expected_counts:
            raise DatasetError(
                "SNAP graph post-check did not match the expected user and edge counts."
            )
    finally:
        if changed:
            cache.bump_version()

    return {
        "dataset": str(dataset_path),
        "stats": parsed.stats.as_dict(),
        "created_users": created_users,
        "created_relationships": created_relationships,
        "deleted_users": deleted_users,
        "deleted_relationships": deleted_relationships,
        "snap_users": actual_counts[0],
        "snap_relationships": actual_counts[1],
        "changed": changed,
    }
