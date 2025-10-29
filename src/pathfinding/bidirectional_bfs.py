"""
Bidirectional BFS Implementation for Social Network Pathfinding
Optimized algorithm for finding shortest paths between users
"""
from collections import deque
from typing import Dict, List, Set, Optional, Tuple, Any
import time
from dataclasses import dataclass

@dataclass
class PathResult:
    """Result of a pathfinding operation"""
    path: Optional[List[str]]
    distance: int
    nodes_explored: int
    execution_time_ms: float
    found: bool

    def __post_init__(self):
        if self.path:
            self.distance = len(self.path) - 1
        else:
            self.distance = -1

class BidirectionalBFS:
    """
    Bidirectional BFS implementation for finding shortest paths
    in social network graphs. Significantly faster than standard BFS
    by searching from both ends simultaneously.
    """

    def __init__(self, graph_db: Any):
        self.graph_db = graph_db
        self.max_depth = 6  # Six degrees of separation

    def find_shortest_path(self, start_user: str, target_user: str) -> PathResult:
        """
        Find shortest path between two users using bidirectional BFS

        Args:
            start_user: Starting user ID
            target_user: Target user ID

        Returns:
            PathResult containing path information
        """
        start_time = time.time()

        # Handle edge cases
        if start_user == target_user:
            return PathResult([start_user], 0, 1, 0.0, True)

        if not self.graph_db.user_exists(start_user) or not self.graph_db.user_exists(target_user):
            return PathResult(None, -1, 0, (time.time() - start_time) * 1000, False)

        # Initialize BFS from both ends
        forward_queue = deque([start_user])
        backward_queue = deque([target_user])

        forward_visited = {start_user: None}  # user -> parent
        backward_visited = {target_user: None}

        forward_depth = {start_user: 0}
        backward_depth = {target_user: 0}

        nodes_explored = 0
        current_depth = 0

        while forward_queue or backward_queue:
            # Alternate between forward and backward search
            # Search from the smaller frontier first (optimization)
            if len(forward_queue) <= len(backward_queue):
                meeting_point = self._expand_frontier(
                    forward_queue, forward_visited, forward_depth, 
                    backward_visited, current_depth
                )
                if meeting_point:
                    path = self._reconstruct_path(
                        start_user, target_user, meeting_point,
                        forward_visited, backward_visited
                    )
                    execution_time = (time.time() - start_time) * 1000
                    return PathResult(path, len(path) - 1, nodes_explored, execution_time, True)

                nodes_explored += len(forward_queue)
            else:
                meeting_point = self._expand_frontier(
                    backward_queue, backward_visited, backward_depth,
                    forward_visited, current_depth
                )
                if meeting_point:
                    path = self._reconstruct_path(
                        start_user, target_user, meeting_point,
                        forward_visited, backward_visited
                    )
                    execution_time = (time.time() - start_time) * 1000
                    return PathResult(path, len(path) - 1, nodes_explored, execution_time, True)

                nodes_explored += len(backward_queue)

            current_depth += 1

            # Prevent infinite search
            if current_depth > self.max_depth:
                break

        # No path found
        execution_time = (time.time() - start_time) * 1000
        return PathResult(None, -1, nodes_explored, execution_time, False)

    def _expand_frontier(self, queue: deque, visited: Dict[str, str], 
                        depths: Dict[str, int], other_visited: Dict[str, str], 
                        current_depth: int) -> Optional[str]:
        """
        Expand one level of the BFS frontier

        Args:
            queue: BFS queue to expand
            visited: Visited nodes for this direction
            depths: Depth of each node
            other_visited: Visited nodes from other direction
            current_depth: Current search depth

        Returns:
            Meeting point if found, None otherwise
        """
        if not queue:
            return None

        next_queue = deque()

        while queue:
            current_user = queue.popleft()

            # Skip if we've gone too deep
            if depths.get(current_user, 0) >= self.max_depth // 2:
                continue

            # Get neighbors from graph database
            neighbors = self.graph_db.get_connections(current_user)

            for neighbor in neighbors:
                # Check if we've found a meeting point
                if neighbor in other_visited:
                    return neighbor

                # Add unvisited neighbors
                if neighbor not in visited:
                    visited[neighbor] = current_user
                    depths[neighbor] = depths[current_user] + 1
                    next_queue.append(neighbor)

        # Update queue for next iteration
        queue.extend(next_queue)
        return None

    def _reconstruct_path(self, start: str, target: str, meeting_point: str,
                         forward_visited: Dict[str, str], 
                         backward_visited: Dict[str, str]) -> List[str]:
        """
        Reconstruct the complete path from start to target through meeting point

        Args:
            start: Start user ID
            target: Target user ID
            meeting_point: Where the two searches met
            forward_visited: Forward search visited nodes
            backward_visited: Backward search visited nodes

        Returns:
            Complete path as list of user IDs
        """
        # Build path from start to meeting point
        forward_path = []
        current = meeting_point
        while current is not None:
            forward_path.append(current)
            current = forward_visited.get(current)
        forward_path.reverse()

        # Build path from meeting point to target
        backward_path = []
        current = backward_visited.get(meeting_point)  # Skip meeting point to avoid duplication
        while current is not None:
            backward_path.append(current)
            current = backward_visited.get(current)

        # Combine paths
        complete_path = forward_path + backward_path
        return complete_path

    def find_all_paths(self, start_user: str, target_user: str, max_paths: int = 5) -> List[PathResult]:
        """
        Find multiple paths between two users (not just the shortest)
        Note: This is computationally expensive and should be used sparingly
        """
        paths = []
        # Implementation would use modified BFS/DFS to find alternative paths
        # For now, return the shortest path
        shortest = self.find_shortest_path(start_user, target_user)
        if shortest.found:
            paths.append(shortest)
        return paths

    def batch_pathfinding(self, queries: List[Tuple[str, str]]) -> Dict[Tuple[str, str], PathResult]:
        """
        Perform multiple pathfinding queries in batch

        Args:
            queries: List of (start_user, target_user) tuples

        Returns:
            Dictionary mapping queries to results
        """
        results = {}
        for start_user, target_user in queries:
            result = self.find_shortest_path(start_user, target_user)
            results[(start_user, target_user)] = result
        return results

    def get_degrees_of_separation(self, start_user: str, target_user: str) -> int:
        """
        Get just the degrees of separation (distance) between two users

        Returns:
            Number of degrees of separation, or -1 if no path exists
        """
        result = self.find_shortest_path(start_user, target_user)
        return result.distance
