"""
User model for the social network pathfinding engine
"""
from dataclasses import dataclass
from typing import Set, Optional
from datetime import datetime

@dataclass
class User:
    """Represents a user in the social network"""

    user_id: str
    username: str
    email: str
    created_at: datetime
    is_active: bool = True

    def __post_init__(self):
        """Initialize user connections set"""
        self.connections: Set[str] = set()

    def add_connection(self, user_id: str) -> bool:
        """Add a connection to another user"""
        if user_id != self.user_id:
            self.connections.add(user_id)
            return True
        return False

    def remove_connection(self, user_id: str) -> bool:
        """Remove a connection to another user"""
        if user_id in self.connections:
            self.connections.remove(user_id)
            return True
        return False

    def get_connections(self) -> Set[str]:
        """Get all user connections"""
        return self.connections.copy()

    def __hash__(self):
        return hash(self.user_id)

    def __eq__(self, other):
        if isinstance(other, User):
            return self.user_id == other.user_id
        return False
