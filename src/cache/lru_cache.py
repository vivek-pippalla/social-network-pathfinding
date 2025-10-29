"""
High-Performance LRU Cache Implementation
Distributed caching layer for pathfinding results
"""
import threading
import time
from typing import Dict, Any, Optional, Tuple
from collections import OrderedDict
from dataclasses import dataclass
import json
import hashlib

@dataclass
class CacheEntry:
    """Represents a cache entry with metadata"""
    value: Any
    timestamp: float
    access_count: int
    ttl: Optional[float] = None  # Time to live in seconds

    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        if self.ttl is None:
            return False
        return time.time() - self.timestamp > self.ttl

    def touch(self):
        """Update access metadata"""
        self.access_count += 1
        self.timestamp = time.time()

class LRUCache:
    """
    Thread-safe LRU Cache with TTL support
    Optimized for high-concurrency pathfinding queries
    """

    def __init__(self, max_size: int = 10000, default_ttl: float = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl  # 1 hour default TTL

        # Thread-safe storage
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()

        # Metrics
        self.hit_count = 0
        self.miss_count = 0
        self.eviction_count = 0
        self.cleanup_count = 0

        # Background cleanup
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5 minutes

    def _generate_key(self, *args) -> str:
        """Generate cache key from arguments"""
        key_string = "|".join(str(arg) for arg in args)
        return hashlib.md5(key_string.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache"""
        with self._lock:
            self._periodic_cleanup()

            if key not in self._cache:
                self.miss_count += 1
                return None

            entry = self._cache[key]

            # Check if expired
            if entry.is_expired():
                del self._cache[key]
                self.miss_count += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.touch()

            self.hit_count += 1
            return entry.value

    def put(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Store value in cache"""
        with self._lock:
            if ttl is None:
                ttl = self.default_ttl

            # Remove if already exists
            if key in self._cache:
                del self._cache[key]

            # Create new entry
            entry = CacheEntry(
                value=value,
                timestamp=time.time(),
                access_count=1,
                ttl=ttl
            )

            self._cache[key] = entry

            # Evict if over capacity
            while len(self._cache) > self.max_size:
                oldest_key, _ = self._cache.popitem(last=False)
                self.eviction_count += 1

    def delete(self, key: str) -> bool:
        """Delete entry from cache"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all cache entries"""
        with self._lock:
            self._cache.clear()
            self.hit_count = 0
            self.miss_count = 0
            self.eviction_count = 0

    def size(self) -> int:
        """Get current cache size"""
        return len(self._cache)

    def hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total_requests = self.hit_count + self.miss_count
        if total_requests == 0:
            return 0.0
        return self.hit_count / total_requests

    def _periodic_cleanup(self) -> None:
        """Remove expired entries periodically"""
        current_time = time.time()
        if current_time - self._last_cleanup < self._cleanup_interval:
            return

        expired_keys = []
        for key, entry in self._cache.items():
            if entry.is_expired():
                expired_keys.append(key)

        for key in expired_keys:
            del self._cache[key]
            self.cleanup_count += 1

        self._last_cleanup = current_time

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hit_count': self.hit_count,
                'miss_count': self.miss_count,
                'hit_rate': self.hit_rate(),
                'eviction_count': self.eviction_count,
                'cleanup_count': self.cleanup_count,
                'memory_usage_percent': (len(self._cache) / self.max_size) * 100
            }

class PathfindingCache:
    """
    Specialized cache for pathfinding results
    Handles path queries with intelligent key generation
    """

    def __init__(self, max_size: int = 50000, path_ttl: float = 1800):  # 30 minutes
        self.cache = LRUCache(max_size, path_ttl)
        self.path_ttl = path_ttl

    def _create_path_key(self, start_user: str, target_user: str) -> str:
        """Create cache key for path query (order-independent)"""
        # Sort users to make key order-independent for undirected paths
        users = sorted([start_user, target_user])
        return f"path:{users[0]}:{users[1]}"

    def get_path(self, start_user: str, target_user: str) -> Optional[Dict]:
        """Get cached path result"""
        key = self._create_path_key(start_user, target_user)
        result = self.cache.get(key)

        if result and start_user != result.get('start_user'):
            # Reverse the path if we got it in opposite direction
            if result.get('path'):
                result = result.copy()
                result['path'] = list(reversed(result['path']))
                result['start_user'], result['target_user'] = result['target_user'], result['start_user']

        return result

    def cache_path(self, start_user: str, target_user: str, path_result: Dict) -> None:
        """Cache path result"""
        key = self._create_path_key(start_user, target_user)

        # Add metadata
        cache_data = path_result.copy()
        cache_data['start_user'] = start_user
        cache_data['target_user'] = target_user
        cache_data['cached_at'] = time.time()

        self.cache.put(key, cache_data, self.path_ttl)

    def invalidate_user_paths(self, user_id: str) -> int:
        """Invalidate all cached paths involving a user (when connections change)"""
        # This is a simplified implementation
        # In production, we'd maintain a user->keys mapping
        invalidated = 0
        keys_to_remove = []

        with self.cache._lock:
            for key in self.cache._cache.keys():
                if key.startswith('path:') and user_id in key:
                    keys_to_remove.append(key)

        for key in keys_to_remove:
            if self.cache.delete(key):
                invalidated += 1

        return invalidated

    def warm_up_cache(self, user_pairs: list) -> int:
        """Pre-populate cache with common path queries"""
        # This would be called with frequently queried pairs
        # Implementation would depend on pathfinding service
        return 0

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        base_stats = self.cache.get_stats()
        base_stats['cache_type'] = 'pathfinding'
        base_stats['path_ttl'] = self.path_ttl
        return base_stats

class DistributedCache:
    """
    Distributed cache coordinator
    In production, this would coordinate multiple cache nodes
    """

    def __init__(self, num_nodes: int = 3):
        self.num_nodes = num_nodes
        self.nodes = [LRUCache(max_size=10000) for _ in range(num_nodes)]
        self.pathfinding_cache = PathfindingCache()

    def _get_node(self, key: str) -> int:
        """Determine which node should handle this key"""
        return hash(key) % self.num_nodes

    def get(self, key: str) -> Optional[Any]:
        """Get value from appropriate cache node"""
        node_id = self._get_node(key)
        return self.nodes[node_id].get(key)

    def put(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Put value in appropriate cache node"""
        node_id = self._get_node(key)
        self.nodes[node_id].put(key, value, ttl)

    def get_cluster_stats(self) -> Dict[str, Any]:
        """Get statistics from all cache nodes"""
        cluster_stats = {
            'num_nodes': self.num_nodes,
            'total_size': sum(node.size() for node in self.nodes),
            'total_hits': sum(node.hit_count for node in self.nodes),
            'total_misses': sum(node.miss_count for node in self.nodes),
            'node_stats': [node.get_stats() for node in self.nodes],
            'pathfinding_cache': self.pathfinding_cache.get_cache_stats()
        }

        total_requests = cluster_stats['total_hits'] + cluster_stats['total_misses']
        cluster_stats['cluster_hit_rate'] = (
            cluster_stats['total_hits'] / total_requests if total_requests > 0 else 0.0
        )

        return cluster_stats
