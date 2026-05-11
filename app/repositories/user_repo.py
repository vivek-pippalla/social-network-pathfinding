import uuid
import logging
from neo4j import Driver
from app.models.schemas import UserCreate

logger = logging.getLogger(__name__)


def create_user(driver: Driver, user: UserCreate) -> dict:
    """Create a new User node in Neo4j and return the created record."""
    user_id = str(uuid.uuid4())[:8]  # short readable ID
    with driver.session() as session:
        result = session.run(
            """
            CREATE (u:User {id: $id, name: $name, email: $email})
            RETURN u
            """,
            id=user_id,
            name=user.name,
            email=user.email,
        )
        record = result.single()
        return dict(record["u"])


def get_user_by_id(driver: Driver, user_id: str) -> dict | None:
    """Fetch a single User node by its id. Returns None if not found."""
    with driver.session() as session:
        result = session.run(
            "MATCH (u:User {id: $id}) RETURN u",
            id=user_id,
        )
        record = result.single()
        return dict(record["u"]) if record else None


def search_users(driver: Driver, query: str) -> list[dict]:
    """Case-insensitive name search. Returns up to 20 results."""
    with driver.session() as session:
        result = session.run(
            """
            MATCH (u:User)
            WHERE toLower(u.name) CONTAINS toLower($q)
            RETURN u
            LIMIT 20
            """,
            q=query,
        )
        return [dict(record["u"]) for record in result]
