import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import redis
from pydantic import BaseModel, ValidationError, model_validator

from app.db.redis_cache import get_client
from app.models.schemas import PathNode

logger = logging.getLogger(__name__)
GRAPH_VERSION_KEY = "graph:version"


class CachedPathPayload(BaseModel):
    state: Literal["path", "not_found"]
    path: list[PathNode] | None = None

    @model_validator(mode="after")
    def validate_state(self):
        if self.state == "path" and not self.path:
            raise ValueError("path cache entries must contain a path")
        if self.state == "not_found" and self.path is not None:
            raise ValueError("negative path cache entries cannot contain a path")
        return self


@dataclass(frozen=True)
class PathCacheLookup:
    version: int | None
    hit: bool
    path: list[dict] | None = None


class CacheService:
    def __init__(
        self,
        redis_provider: Callable[[], redis.Redis] = get_client,
        *,
        positive_ttl: int = 300,
        negative_ttl: int = 60,
        warning_interval_seconds: float = 30.0,
    ):
        self._redis_provider = redis_provider
        self._positive_ttl = positive_ttl
        self._negative_ttl = negative_ttl
        self._warning_interval_seconds = warning_interval_seconds
        self._warning_lock = threading.Lock()
        self._last_warning: dict[str, float] = {}

    @staticmethod
    def path_key(version: int, start_id: str, end_id: str) -> str:
        low_id, high_id = sorted((start_id, end_id))
        return f"path:v{version}:{low_id}:{high_id}"

    def _warn(self, operation: str) -> None:
        now = time.monotonic()
        with self._warning_lock:
            previous = self._last_warning.get(operation)
            if previous is not None and now - previous < self._warning_interval_seconds:
                return
            self._last_warning[operation] = now
        logger.warning("Redis cache operation failed", extra={"operation": operation})

    def _get_version(self) -> int | None:
        try:
            raw_version = self._redis_provider().get(GRAPH_VERSION_KEY)
            version = int(raw_version or 0)
            if version < 0:
                raise ValueError("graph version cannot be negative")
            return version
        except redis.RedisError:
            self._warn("read_version")
            return None
        except (TypeError, ValueError):
            self._warn("read_version")
            return None

    def get_path(self, start_id: str, end_id: str) -> PathCacheLookup:
        version = self._get_version()
        if version is None:
            return PathCacheLookup(version=None, hit=False)

        key = self.path_key(version, start_id, end_id)
        try:
            encoded = self._redis_provider().get(key)
        except redis.RedisError:
            self._warn("read_path")
            return PathCacheLookup(version=version, hit=False)
        if encoded is None:
            return PathCacheLookup(version=version, hit=False)

        try:
            payload = CachedPathPayload.model_validate_json(encoded)
            if payload.state == "not_found":
                return PathCacheLookup(version=version, hit=True)
            low_id, high_id = sorted((start_id, end_id))
            path = [node.model_dump() for node in payload.path or []]
            if path[0]["id"] != low_id or path[-1]["id"] != high_id:
                raise ValueError("cached path endpoints do not match its key")
            if start_id != low_id:
                path.reverse()
            return PathCacheLookup(version=version, hit=True, path=path)
        except (ValidationError, ValueError, TypeError):
            self._warn("decode_path")
            return PathCacheLookup(version=version, hit=False)

    def set_path(
        self,
        start_id: str,
        end_id: str,
        path: list[dict] | None,
        *,
        version: int | None,
    ) -> None:
        if version is None:
            return

        if path is None:
            payload = CachedPathPayload(state="not_found")
            ttl = self._negative_ttl
        else:
            canonical_path = list(path)
            if start_id > end_id:
                canonical_path.reverse()
            payload = CachedPathPayload(
                state="path",
                path=[PathNode.model_validate(node) for node in canonical_path],
            )
            ttl = self._positive_ttl

        key = self.path_key(version, start_id, end_id)
        try:
            self._redis_provider().setex(key, ttl, payload.model_dump_json())
        except redis.RedisError:
            self._warn("write_path")

    def bump_version(self) -> None:
        try:
            self._redis_provider().incr(GRAPH_VERSION_KEY)
        except redis.RedisError:
            self._warn("bump_version")
