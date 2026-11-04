"""Measure path API latency against an already-running stack; this script seeds nothing."""

import argparse
import json
import math
import os
import platform
import statistics
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


def percentile(samples: list[float], fraction: float) -> float:
    ordered = sorted(samples)
    if not ordered:
        raise ValueError("at least one sample is required")
    rank = max(1, math.ceil(fraction * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def display_target(base_url: str) -> str:
    endpoint = urlsplit(base_url)
    host = endpoint.hostname or "unset"
    if ":" in host:
        host = f"[{host}]"
    port = f":{endpoint.port}" if endpoint.port is not None else ""
    return f"{endpoint.scheme}://{host}{port}"


def request_path(base_url: str, token: str, start_id: str, end_id: str) -> float:
    path = f"/api/v1/path/{quote(start_id, safe='-_')}/{quote(end_id, safe='-_')}"
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=10) as response:
            body = response.read()
            status = response.status
    except HTTPError as exc:
        raise RuntimeError(f"path request returned HTTP {exc.code}") from None
    except URLError as exc:
        raise RuntimeError(f"path request failed: {exc.reason}") from None
    elapsed_ms = (time.perf_counter() - started) * 1000
    if status != 200:
        raise RuntimeError(f"path request returned HTTP {status}")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise RuntimeError("path endpoint did not return JSON") from None
    if not isinstance(payload, dict) or "path" not in payload:
        raise RuntimeError("path endpoint returned an unexpected response")
    return elapsed_ms


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url", default=os.getenv("BASE_URL", "http://127.0.0.1:8000")
    )
    parser.add_argument("--token", default=os.getenv("ACCESS_TOKEN"))
    parser.add_argument("--start", default=os.getenv("START_USER_ID"))
    parser.add_argument("--end", default=os.getenv("END_USER_ID"))
    parser.add_argument("--iterations", type=int, default=30)
    args = parser.parse_args()
    if not args.token or not args.start or not args.end:
        parser.error("provide ACCESS_TOKEN, START_USER_ID, END_USER_ID or their flags")
    if args.iterations < 1:
        parser.error("--iterations must be at least 1")

    first_request = request_path(args.base_url, args.token, args.start, args.end)
    repeated = [
        request_path(args.base_url, args.token, args.start, args.end)
        for _ in range(args.iterations)
    ]
    neo4j_host = urlsplit(os.getenv("NEO4J_URI", "bolt://localhost:7687"))

    print(f"Machine: {platform.platform()} | Python {platform.python_version()}")
    print(
        "Neo4j settings: "
        f"endpoint={neo4j_host.hostname or 'unset'}:{neo4j_host.port or 'default'} "
        f"NEO4J_VERSION={os.getenv('NEO4J_VERSION', 'not supplied')} "
        f"NEO4J_HEAP_MAX={os.getenv('NEO4J_HEAP_MAX', 'not supplied')} "
        f"NEO4J_PAGECACHE={os.getenv('NEO4J_PAGECACHE', 'not supplied')} "
        f"MAX_PATH_DEPTH={os.getenv('MAX_PATH_DEPTH', '6')} "
        f"NEO4J_QUERY_TIMEOUT_SECONDS={os.getenv('NEO4J_QUERY_TIMEOUT_SECONDS', '5')}"
    )
    print(f"API: {display_target(args.base_url)} | iterations={args.iterations}")
    print(
        "first request (database cache state uncontrolled): "
        f"p50={statistics.median([first_request]):.2f}ms "
        f"p95={percentile([first_request], 0.95):.2f}ms"
    )
    print(
        f"repeated requests (n={len(repeated)}): "
        f"p50={statistics.median(repeated):.2f}ms "
        f"p95={percentile(repeated, 0.95):.2f}ms"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
