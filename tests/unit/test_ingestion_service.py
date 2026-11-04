import gzip
import hashlib
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.cli import _confirm_destructive_options
from app.cli import _parser
from app.services import ingestion_service


def _write_gzip(path: Path, content: bytes) -> Path:
    with gzip.open(path, "wb") as compressed:
        compressed.write(content)
    return path


def test_parser_counts_comments_blank_lines_malformed_rows_self_loops_and_duplicates(
    tmp_path,
):
    source = _write_gzip(
        tmp_path / "edges.txt.gz",
        (b"# header\r\n\r\n0 1\r\n1 0\r\n2 2\r\n3 4 5\r\n\xc3\xb1 3\r\n0 2\r\n"),
    )

    parsed = ingestion_service.parse_edge_file(source)

    assert parsed.user_ids == ("0", "1", "2")
    assert parsed.edges == (("0", "1"), ("0", "2"))
    assert parsed.stats.as_dict() == {
        "total_lines": 8,
        "valid_edges": 2,
        "malformed": 2,
        "self_loops": 1,
        "duplicates": 1,
        "ignored": 2,
        "unique_users": 3,
        "rejected": 4,
    }


def test_parser_accepts_plain_text_and_rejects_invalid_ids(tmp_path):
    source = tmp_path / "edges.txt"
    source.write_bytes(b"a-b c_1\ninvalid/one valid\n" + "é z\n".encode())

    parsed = ingestion_service.parse_edge_file(source)

    assert parsed.edges == (("a-b", "c_1"),)
    assert parsed.stats.malformed == 2


def test_expected_sha_matches_the_existing_snap_archive():
    archive = (
        Path(__file__).resolve().parents[2] / "scripts" / "facebook_combined.txt.gz"
    )

    assert ingestion_service.sha256_file(archive) == ingestion_service.DATASET_SHA256


def test_dataset_download_verifies_digest_before_atomic_cache_write(
    tmp_path, monkeypatch
):
    contents = b"verified dataset bytes"
    expected_sha = hashlib.sha256(contents).hexdigest()

    def download(_url, target):
        Path(target).write_bytes(contents)

    monkeypatch.setattr(ingestion_service.urllib.request, "urlretrieve", download)
    target = tmp_path / "cache" / "facebook.txt.gz"

    resolved = ingestion_service.ensure_dataset_file(
        target, url="https://snap.example/dataset.gz", expected_sha256=expected_sha
    )

    assert resolved == target
    assert target.read_bytes() == contents


def test_corrupt_download_is_removed_and_never_cached(tmp_path, monkeypatch):
    def download(_url, target):
        Path(target).write_bytes(b"corrupt")

    monkeypatch.setattr(ingestion_service.urllib.request, "urlretrieve", download)
    target = tmp_path / "cache" / "facebook.txt.gz"

    with pytest.raises(ingestion_service.DatasetError, match="SHA-256"):
        ingestion_service.ensure_dataset_file(
            target, url="https://snap.example/dataset.gz", expected_sha256="0" * 64
        )

    assert not target.exists()
    assert list(target.parent.iterdir()) == []


def test_checksum_mismatch_is_rejected_before_schema_or_graph_writes(tmp_path):
    bad_file = tmp_path / "bad.txt.gz"
    _write_gzip(bad_file, b"0 1\n")
    ensure_schema = Mock()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(ingestion_service, "ensure_schema", ensure_schema)
    cache = Mock()
    try:
        with pytest.raises(ingestion_service.DatasetError, match="SHA-256"):
            ingestion_service.run_ingestion(
                object(),
                cache,
                bad_file,
                expected_sha256="0" * 64,
            )
    finally:
        monkeypatch.undo()

    ensure_schema.assert_not_called()
    cache.bump_version.assert_not_called()


def test_ingestion_uses_creation_counters_batches_and_bumps_once_on_change(
    tmp_path, monkeypatch
):
    source = _write_gzip(tmp_path / "edges.txt.gz", b"0 1\n0 2\n")
    expected_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    ensure_schema = Mock()
    monkeypatch.setattr(ingestion_service, "ensure_schema", ensure_schema)
    monkeypatch.setattr(
        ingestion_service.ingestion_repo,
        "merge_snap_users",
        Mock(side_effect=[2, 1]),
    )
    monkeypatch.setattr(
        ingestion_service.ingestion_repo,
        "merge_snap_edges",
        Mock(return_value=2),
    )
    monkeypatch.setattr(
        ingestion_service.ingestion_repo, "snap_graph_counts", Mock(return_value=(3, 2))
    )
    cache = Mock()

    result = ingestion_service.run_ingestion(
        object(),
        cache,
        source,
        batch_size=2,
        expected_sha256=expected_sha,
        expected_counts=(3, 2),
    )

    assert result["created_users"] == 3
    assert result["created_relationships"] == 2
    assert result["snap_users"] == 3
    assert result["snap_relationships"] == 2
    assert result["changed"] is True
    assert ensure_schema.call_count == 1
    assert cache.bump_version.call_count == 1


def test_idempotent_ingestion_does_not_bump_cache_version(tmp_path, monkeypatch):
    source = _write_gzip(tmp_path / "edges.txt.gz", b"0 1\n")
    expected_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    monkeypatch.setattr(ingestion_service, "ensure_schema", Mock())
    monkeypatch.setattr(
        ingestion_service.ingestion_repo, "merge_snap_users", Mock(return_value=0)
    )
    monkeypatch.setattr(
        ingestion_service.ingestion_repo, "merge_snap_edges", Mock(return_value=0)
    )
    monkeypatch.setattr(
        ingestion_service.ingestion_repo, "snap_graph_counts", Mock(return_value=(2, 1))
    )
    cache = Mock()

    result = ingestion_service.run_ingestion(
        object(),
        cache,
        source,
        expected_sha256=expected_sha,
        expected_counts=(2, 1),
    )

    assert result["changed"] is False
    cache.bump_version.assert_not_called()


def test_reset_requires_explicit_confirmation_and_wipe_all_is_separate():
    with pytest.raises(ValueError, match="--yes-i-am-sure"):
        _confirm_destructive_options(
            reset=True,
            wipe_all=False,
            yes_i_am_sure=False,
            is_interactive=False,
        )
    with pytest.raises(ValueError, match="requires --reset"):
        _confirm_destructive_options(
            reset=False,
            wipe_all=True,
            yes_i_am_sure=True,
            is_interactive=False,
        )
    with pytest.raises(ValueError, match="did not match"):
        _confirm_destructive_options(
            reset=True,
            wipe_all=True,
            yes_i_am_sure=False,
            is_interactive=True,
            read_confirmation=lambda _prompt: "RESET SNAP DATA",
        )


def test_interactive_reset_requires_exact_scope_phrase():
    _confirm_destructive_options(
        reset=True,
        wipe_all=False,
        yes_i_am_sure=False,
        is_interactive=True,
        read_confirmation=lambda _prompt: "RESET SNAP DATA",
    )


def test_cli_exposes_only_the_planned_operator_commands():
    parser = _parser()

    assert set(parser._subparsers._group_actions[0].choices) == {
        "schema",
        "ingest",
        "reset-cache",
        "demo-user",
    }
