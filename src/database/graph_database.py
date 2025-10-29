"""
Distributed Graph Database Layer
Implements the core graph storage and retrieval functionality
"""
import threading
import uuid
from typing import Dict, List, Set, Optional, Tuple
from datetime import datetime
from collections import defaultdict
import json

# Import our models (in a real implementation, these would be proper imports)
from models.user import User
from models.connection import Connection, ConnectionType
from database.sharding import DistributedGraphSharding, GraphShard

class GraphDatabase:
    """
    Core distributed graph database for social network
    Handles user storage, connections, and provides query interface
    """

    def __init__(self, num_shards: int = 4):
        self.num_shards = num_shards
        self.sharding = DistributedGraphSharding(num_shards)

        # Thread safety
        self._lock = threading.RLock()

        # Metrics
        self.query_count = 0
        self.connection_count = 0

        # In-memory user storage (in production, this would be persistent)
        self._users: Dict[str, 'User'] = {}
        self._connections: Dict[str, Set[str]] = defaultdict(set)

    def add_user(self, username: str, email: str, user_id: Optional[str] = None) -> str:
        """Add a new user to the graph database"""
        with self._lock:
            if user_id is None:
                user_id = str(uuid.uuid4())

            # Create user object (simplified for demo)
            user_data = {
                'user_id': user_id,
                'username': username,
                'email': email,
                'created_at': datetime.now().isoformat(),
                'is_active': True,
                'connections': set()
            }

            self._users[user_id] = user_data

            # Add to appropriate shard
            # user = User(user_id, username, email, datetime.now())
            # self.sharding.add_user(user)

            return user_id

    def get_user(self, user_id: str) -> Optional[Dict]:
        """Retrieve user by ID"""
        return self._users.get(user_id)

    def add_connection(self, from_user_id: str, to_user_id: str) -> bool:
        """Add a bidirectional connection between two users"""
        with self._lock:
            # Validate users exist
            if from_user_id not in self._users or to_user_id not in self._users:
                return False

            if from_user_id == to_user_id:
                return False

            # Add bidirectional connections
            self._connections[from_user_id].add(to_user_id)
            self._connections[to_user_id].add(from_user_id)

            # Update user objects
            self._users[from_user_id]['connections'].add(to_user_id)
            self._users[to_user_id]['connections'].add(from_user_id)

            # Add to sharding system
            self.sharding.add_connection(from_user_id, to_user_id)

            self.connection_count += 1
            return True

    def remove_connection(self, from_user_id: str, to_user_id: str) -> bool:
        """Remove connection between two users"""
        with self._lock:
            if from_user_id not in self._connections:
                return False

            if to_user_id in self._connections[from_user_id]:
                self._connections[from_user_id].remove(to_user_id)
                self._connections[to_user_id].remove(from_user_id)

                self._users[from_user_id]['connections'].discard(to_user_id)
                self._users[to_user_id]['connections'].discard(from_user_id)

                return True
            return False

    def get_connections(self, user_id: str) -> Set[str]:
        """Get all connections for a user"""
        self.query_count += 1
        return self._connections.get(user_id, set()).copy()

    def get_connection_count(self, user_id: str) -> int:
        """Get number of connections for a user"""
        return len(self._connections.get(user_id, set()))

    def user_exists(self, user_id: str) -> bool:
        """Check if user exists in the database"""
        return user_id in self._users

    def get_mutual_connections(self, user1_id: str, user2_id: str) -> Set[str]:
        """Get mutual connections between two users"""
        connections1 = self.get_connections(user1_id)
        connections2 = self.get_connections(user2_id)
        return connections1.intersection(connections2)

    def get_database_stats(self) -> Dict:
        """Get database statistics"""
        with self._lock:
            total_connections = sum(len(conns) for conns in self._connections.values()) // 2

            stats = {
                'total_users': len(self._users),
                'total_connections': total_connections,
                'query_count': self.query_count,
                'average_connections': total_connections / max(len(self._users), 1),
                'num_shards': self.num_shards,
                'cross_shard_ratio': self.sharding.get_cross_shard_ratio(),
                'shard_stats': self.sharding.get_shard_stats()
            }

            return stats

    def bulk_add_users(self, users_data: List[Dict]) -> List[str]:
        """Bulk add multiple users"""
        user_ids = []
        for user_data in users_data:
            user_id = self.add_user(
                username=user_data['username'],
                email=user_data['email'],
                user_id=user_data.get('user_id')
            )
            user_ids.append(user_id)
        return user_ids

    def bulk_add_connections(self, connections: List[Tuple[str, str]]) -> int:
        """Bulk add multiple connections"""
        successful = 0
        for from_user, to_user in connections:
            if self.add_connection(from_user, to_user):
                successful += 1
        return successful

    def export_graph(self) -> Dict:
        """Export graph data (for persistence/backup)"""
        with self._lock:
            return {
                'users': {uid: {**data, 'connections': list(data['connections'])} 
                         for uid, data in self._users.items()},
                'connections': {uid: list(conns) for uid, conns in self._connections.items()},
                'stats': self.get_database_stats()
            }

    def import_graph(self, graph_data: Dict) -> bool:
        """Import graph data (for loading from backup)"""
        try:
            with self._lock:
                # Clear existing data
                self._users.clear()
                self._connections.clear()

                # Import users
                for user_id, user_data in graph_data['users'].items():
                    user_data['connections'] = set(user_data['connections'])
                    self._users[user_id] = user_data

                # Import connections
                for user_id, connections in graph_data['connections'].items():
                    self._connections[user_id] = set(connections)

                return True
        except Exception as e:
            print(f"Error importing graph data: {e}")
            return False
