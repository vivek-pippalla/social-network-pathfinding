from collections.abc import Callable
from functools import wraps
from time import perf_counter
from typing import ParamSpec, TypeVar

from prometheus_client import Counter, Histogram

P = ParamSpec("P")
R = TypeVar("R")

PATH_CACHE_OPERATIONS = Counter(
    "path_cache_operations",
    "Path cache lookups by outcome.",
    labelnames=("result",),
)
PATH_REQUEST_DURATION = Histogram(
    "path_request_duration_seconds",
    "Path request duration by whether its result came from cache.",
    labelnames=("cache",),
)
FRIEND_MUTATIONS = Counter(
    "friend_mutations",
    "Friendship mutation outcomes.",
    labelnames=("outcome",),
)
AUTH_FAILURES = Counter(
    "auth_failures",
    "Authentication failures by operation and safe reason.",
    labelnames=("operation", "reason"),
)
RATE_LIMIT_REJECTIONS = Counter(
    "rate_limit_rejections",
    "Rate limit rejections by bounded operation name.",
    labelnames=("operation",),
)
NEO4J_QUERY_DURATION = Histogram(
    "neo4j_query_duration_seconds",
    "Neo4j repository operation duration.",
    labelnames=("operation",),
)


def observe_neo4j_query(operation: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Record a repository operation using a fixed, low-cardinality label."""

    def decorate(function: Callable[P, R]) -> Callable[P, R]:
        @wraps(function)
        def measured(*args: P.args, **kwargs: P.kwargs) -> R:
            started = perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                NEO4J_QUERY_DURATION.labels(operation=operation).observe(
                    perf_counter() - started
                )

        return measured

    return decorate
