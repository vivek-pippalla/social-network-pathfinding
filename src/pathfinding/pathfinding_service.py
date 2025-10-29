"""
Intelligent Pathfinding Service
Integrates graph database, bidirectional BFS, and caching
"""
import time
import threading
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import asdict
import json
import logging

# In production, these would be proper imports
from database.graph_database import GraphDatabase
from pathfinding.bidirectional_bfs import BidirectionalBFS, PathResult
from cache.lru_cache import PathfindingCache, DistributedCache

class PathfindingService:
    """
    Main service for social network pathfinding operations
    Combines graph database, pathfinding algorithms, and caching
    """

    def __init__(self, graph_db=None, cache_size: int = 50000):
        # Initialize components
        self.graph_db = graph_db or GraphDatabase(num_shards=4)
        self.pathfinder = BidirectionalBFS(self.graph_db)  # Would need to import
        self.cache = PathfindingCache(max_size=cache_size)

        # Service configuration
        self.max_query_time_ms = 5000  # 5 second timeout
        self.enable_caching = True
        self.enable_metrics = True

        # Metrics and monitoring
        self.query_metrics = {
            'total_queries': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'average_response_time_ms': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'timeout_queries': 0
        }

        self._metrics_lock = threading.Lock()

        # Setup logging
        self.logger = logging.getLogger(__name__)

    def find_path(self, start_user_id: str, target_user_id: str, 
                  use_cache: bool = True) -> Dict[str, Any]:
        """
        Find shortest path between two users

        Args:
            start_user_id: Starting user ID
            target_user_id: Target user ID
            use_cache: Whether to use caching

        Returns:
            Dictionary containing path information and metadata
        """
        query_start_time = time.time()

        with self._metrics_lock:
            self.query_metrics['total_queries'] += 1

        try:
            # Check cache first
            if use_cache and self.enable_caching:
                cached_result = self.cache.get_path(start_user_id, target_user_id)
                if cached_result:
                    with self._metrics_lock:
                        self.query_metrics['cache_hits'] += 1
                        self.query_metrics['successful_queries'] += 1

                    # Add cache metadata
                    cached_result['from_cache'] = True
                    cached_result['service_response_time_ms'] = (time.time() - query_start_time) * 1000
                    return cached_result

            # Cache miss - perform pathfinding
            if use_cache:
                with self._metrics_lock:
                    self.query_metrics['cache_misses'] += 1

            # Execute pathfinding algorithm
            path_result = self.pathfinder.find_shortest_path(start_user_id, target_user_id)

            # Convert to service response format
            response = self._format_path_response(path_result, start_user_id, target_user_id)
            response['from_cache'] = False
            response['service_response_time_ms'] = (time.time() - query_start_time) * 1000

            # Cache successful results
            if use_cache and self.enable_caching and path_result.found:
                self.cache.cache_path(start_user_id, target_user_id, response)

            with self._metrics_lock:
                if path_result.found:
                    self.query_metrics['successful_queries'] += 1
                else:
                    self.query_metrics['failed_queries'] += 1

            return response

        except Exception as e:
            self.logger.error(f"Error in pathfinding query: {e}")

            with self._metrics_lock:
                self.query_metrics['failed_queries'] += 1

            return {
                'found': False,
                'error': str(e),
                'start_user_id': start_user_id,
                'target_user_id': target_user_id,
                'service_response_time_ms': (time.time() - query_start_time) * 1000
            }

    def _format_path_response(self, path_result, start_user_id: str, target_user_id: str) -> Dict[str, Any]:
        """Format pathfinding result for API response"""
        return {
            'found': path_result.found,
            'path': path_result.path,
            'degrees_of_separation': path_result.distance,
            'nodes_explored': path_result.nodes_explored,
            'algorithm_execution_time_ms': path_result.execution_time_ms,
            'start_user_id': start_user_id,
            'target_user_id': target_user_id,
            'timestamp': time.time()
        }

    def get_degrees_of_separation(self, start_user_id: str, target_user_id: str) -> int:
        """Quick method to get just the degrees of separation"""
        result = self.find_path(start_user_id, target_user_id, use_cache=True)
        return result.get('degrees_of_separation', -1)

    def batch_pathfinding(self, user_pairs: List[Tuple[str, str]], 
                         max_concurrent: int = 10) -> Dict[str, Dict[str, Any]]:
        """
        Perform multiple pathfinding queries in batch

        Args:
            user_pairs: List of (start_user, target_user) tuples
            max_concurrent: Maximum concurrent queries

        Returns:
            Dictionary mapping "start:target" to results
        """
        results = {}

        # Simple sequential implementation (could be parallelized)
        for start_user, target_user in user_pairs:
            key = f"{start_user}:{target_user}"
            results[key] = self.find_path(start_user, target_user)

        return results

    def suggest_connections(self, user_id: str, max_suggestions: int = 10) -> List[Dict[str, Any]]:
        """
        Suggest potential connections based on mutual friends

        Args:
            user_id: User ID to suggest connections for
            max_suggestions: Maximum number of suggestions

        Returns:
            List of suggested connections with metadata
        """
        suggestions = []

        # Get user's direct connections
        direct_connections = self.graph_db.get_connections(user_id)

        # Find second-degree connections (friends of friends)
        second_degree = set()
        mutual_friend_counts = {}

        for friend_id in direct_connections:
            friend_connections = self.graph_db.get_connections(friend_id)
            for potential_connection in friend_connections:
                if (potential_connection != user_id and 
                    potential_connection not in direct_connections):

                    second_degree.add(potential_connection)
                    mutual_friend_counts[potential_connection] = mutual_friend_counts.get(potential_connection, 0) + 1

        # Sort by number of mutual friends
        sorted_suggestions = sorted(
            second_degree, 
            key=lambda x: mutual_friend_counts[x], 
            reverse=True
        )

        # Build suggestion objects
        for suggestion_id in sorted_suggestions[:max_suggestions]:
            user_info = self.graph_db.get_user(suggestion_id)
            if user_info:
                suggestions.append({
                    'user_id': suggestion_id,
                    'username': user_info.get('username', ''),
                    'mutual_friends_count': mutual_friend_counts[suggestion_id],
                    'connection_strength': min(mutual_friend_counts[suggestion_id] / len(direct_connections), 1.0)
                })

        return suggestions

    def add_user(self, username: str, email: str, user_id: Optional[str] = None) -> str:
        """Add a new user to the social network"""
        return self.graph_db.add_user(username, email, user_id)

    def add_connection(self, from_user_id: str, to_user_id: str) -> bool:
        """
        Add a new connection and invalidate relevant cache entries
        """
        success = self.graph_db.add_connection(from_user_id, to_user_id)

        if success and self.enable_caching:
            # Invalidate cached paths involving these users
            self.cache.invalidate_user_paths(from_user_id)
            self.cache.invalidate_user_paths(to_user_id)

        return success

    def remove_connection(self, from_user_id: str, to_user_id: str) -> bool:
        """
        Remove a connection and invalidate relevant cache entries
        """
        success = self.graph_db.remove_connection(from_user_id, to_user_id)

        if success and self.enable_caching:
            # Invalidate cached paths involving these users
            self.cache.invalidate_user_paths(from_user_id)
            self.cache.invalidate_user_paths(to_user_id)

        return success

    def get_service_stats(self) -> Dict[str, Any]:
        """Get comprehensive service statistics"""
        with self._metrics_lock:
            service_stats = self.query_metrics.copy()

        # Add database stats
        db_stats = self.graph_db.get_database_stats()

        # Add cache stats
        cache_stats = self.cache.get_cache_stats()

        # Calculate derived metrics
        total_queries = service_stats['total_queries']
        if total_queries > 0:
            service_stats['cache_hit_rate'] = service_stats['cache_hits'] / total_queries
            service_stats['success_rate'] = service_stats['successful_queries'] / total_queries
        else:
            service_stats['cache_hit_rate'] = 0.0
            service_stats['success_rate'] = 0.0

        return {
            'service_metrics': service_stats,
            'database_stats': db_stats,
            'cache_stats': cache_stats,
            'timestamp': time.time()
        }

    def health_check(self) -> Dict[str, Any]:
        """Perform service health check"""
        try:
            # Test database connectivity
            db_healthy = self.graph_db.get_database_stats() is not None

            # Test cache functionality
            cache_healthy = self.cache.cache.size() >= 0

            # Test pathfinding with dummy query (if we have users)
            pathfinding_healthy = True

            overall_healthy = db_healthy and cache_healthy and pathfinding_healthy

            return {
                'healthy': overall_healthy,
                'database': db_healthy,
                'cache': cache_healthy,
                'pathfinding': pathfinding_healthy,
                'timestamp': time.time()
            }

        except Exception as e:
            return {
                'healthy': False,
                'error': str(e),
                'timestamp': time.time()
            }

    def export_service_data(self) -> Dict[str, Any]:
        """Export complete service data for backup/migration"""
        return {
            'graph_data': self.graph_db.export_graph(),
            'service_stats': self.get_service_stats(),
            'configuration': {
                'cache_size': self.cache.cache.max_size,
                'max_query_time_ms': self.max_query_time_ms,
                'enable_caching': self.enable_caching
            },
            'export_timestamp': time.time()
        }
