"""
Graph sharding implementation for distributed social network
Implements edge-cut sharding strategy to distribute graph data
"""
import hashlib
from typing import Dict, List, Set, Optional, Tuple
from enum import Enum
from models.user import User
class ShardingStrategy(Enum):
    """Different sharding strategies"""
    HASH_BASED = "hash_based"
    RANGE_BASED = "range_based"
    EDGE_CUT = "edge_cut"
    VERTEX_CUT = "vertex_cut"

class GraphShard:
    """Represents a single shard of the distributed graph"""

    def __init__(self, shard_id: int, total_shards: int):
        self.shard_id = shard_id
        self.total_shards = total_shards
        self.users: Dict[str, 'User'] = {}
        self.local_edges: Dict[str, Set[str]] = {}
        self.remote_edges: Dict[str, Set[Tuple[str, int]]] = {}  # (user_id, target_shard)

    def add_user(self, user: 'User') -> bool:
        """Add user to this shard"""
        if user.user_id not in self.users:
            self.users[user.user_id] = user
            self.local_edges[user.user_id] = set()
            self.remote_edges[user.user_id] = set()
            return True
        return False

    def add_edge(self, from_user: str, to_user: str, target_shard: Optional[int] = None):
        """Add edge, determining if it's local or remote"""
        if target_shard is None or target_shard == self.shard_id:
            # Local edge
            self.local_edges.setdefault(from_user, set()).add(to_user)
        else:
            # Remote edge
            self.remote_edges.setdefault(from_user, set()).add((to_user, target_shard))

    def get_neighbors(self, user_id: str) -> Tuple[Set[str], Set[Tuple[str, int]]]:
        """Get local and remote neighbors for a user"""
        local = self.local_edges.get(user_id, set())
        remote = self.remote_edges.get(user_id, set())
        return local, remote

    def size(self) -> int:
        """Get number of users in this shard"""
        return len(self.users)

class DistributedGraphSharding:
    """Manages sharding of the social network graph"""

    def __init__(self, num_shards: int = 4, strategy: ShardingStrategy = ShardingStrategy.HASH_BASED):
        self.num_shards = num_shards
        self.strategy = strategy
        self.shards: Dict[int, GraphShard] = {}

        # Initialize shards
        for i in range(num_shards):
            self.shards[i] = GraphShard(i, num_shards)

    def _hash_user_id(self, user_id: str) -> int:
        """Hash user ID to determine shard"""
        return int(hashlib.md5(user_id.encode()).hexdigest(), 16) % self.num_shards

    def get_shard_for_user(self, user_id: str) -> int:
        """Determine which shard a user belongs to"""
        if self.strategy == ShardingStrategy.HASH_BASED:
            return self._hash_user_id(user_id)
        elif self.strategy == ShardingStrategy.RANGE_BASED:
            # Simple range-based sharding
            user_hash = hash(user_id)
            return abs(user_hash) % self.num_shards
        else:
            return self._hash_user_id(user_id)  # Default to hash-based

    def add_user(self, user: 'User') -> bool:
        """Add user to appropriate shard"""
        shard_id = self.get_shard_for_user(user.user_id)
        return self.shards[shard_id].add_user(user)

    def add_connection(self, from_user_id: str, to_user_id: str):
        """Add connection, handling cross-shard edges"""
        from_shard = self.get_shard_for_user(from_user_id)
        to_shard = self.get_shard_for_user(to_user_id)

        # Add forward edge
        self.shards[from_shard].add_edge(from_user_id, to_user_id, to_shard)

        # Add reverse edge for bidirectional graph
        self.shards[to_shard].add_edge(to_user_id, from_user_id, from_shard)

    def get_shard(self, shard_id: int) -> Optional[GraphShard]:
        """Get shard by ID"""
        return self.shards.get(shard_id)

    def get_user_neighbors(self, user_id: str) -> Tuple[Set[str], Set[Tuple[str, int]]]:
        """Get neighbors for a user across shards"""
        shard_id = self.get_shard_for_user(user_id)
        shard = self.shards[shard_id]
        return shard.get_neighbors(user_id)

    def get_cross_shard_ratio(self) -> float:
        """Calculate ratio of cross-shard edges (for performance monitoring)"""
        total_edges = 0
        cross_shard_edges = 0

        for shard in self.shards.values():
            for user_id in shard.users:
                local, remote = shard.get_neighbors(user_id)
                total_edges += len(local) + len(remote)
                cross_shard_edges += len(remote)

        return cross_shard_edges / total_edges if total_edges > 0 else 0.0

    def get_shard_stats(self) -> Dict[int, Dict[str, int]]:
        """Get statistics for each shard"""
        stats = {}
        for shard_id, shard in self.shards.items():
            local_edges = sum(len(edges) for edges in shard.local_edges.values())
            remote_edges = sum(len(edges) for edges in shard.remote_edges.values())

            stats[shard_id] = {
                'users': shard.size(),
                'local_edges': local_edges,
                'remote_edges': remote_edges,
                'total_edges': local_edges + remote_edges
            }

        return stats
