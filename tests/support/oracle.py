from collections import deque
from collections.abc import Iterable, Mapping


def bfs_shortest_path(
    adjacency: Mapping[str, Iterable[str]],
    start: str,
    end: str,
    max_depth: int | None = None,
) -> list[str] | None:
    """Return an independent shortest path, bounded by edge count if requested."""
    if start not in adjacency or end not in adjacency:
        return None
    if start == end:
        return [start]

    queue = deque([(start, [start])])
    visited = {start}
    while queue:
        node, path = queue.popleft()
        depth = len(path) - 1
        if max_depth is not None and depth >= max_depth:
            continue
        for neighbor in sorted(set(adjacency.get(node, ()))):
            if neighbor in visited:
                continue
            next_path = [*path, neighbor]
            if neighbor == end:
                return next_path
            visited.add(neighbor)
            queue.append((neighbor, next_path))
    return None
