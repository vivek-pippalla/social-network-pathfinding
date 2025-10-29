"""
Connection model for managing relationships between users
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class ConnectionType(Enum):
    """Types of connections between users"""
    FRIEND = "friend"
    FOLLOW = "follow"
    BLOCK = "block"

@dataclass
class Connection:
    """Represents a connection between two users"""

    from_user_id: str
    to_user_id: str
    connection_type: ConnectionType
    created_at: datetime
    weight: float = 1.0  # For weighted pathfinding

    def __post_init__(self):
        """Validate connection"""
        if self.from_user_id == self.to_user_id:
            raise ValueError("Users cannot connect to themselves")

    def reverse(self) -> 'Connection':
        """Create reverse connection for bidirectional relationships"""
        return Connection(
            from_user_id=self.to_user_id,
            to_user_id=self.from_user_id,
            connection_type=self.connection_type,
            created_at=self.created_at,
            weight=self.weight
        )

    def __hash__(self):
        return hash((self.from_user_id, self.to_user_id))

    def __eq__(self, other):
        if isinstance(other, Connection):
            return (self.from_user_id == other.from_user_id and 
                   self.to_user_id == other.to_user_id)
        return False
