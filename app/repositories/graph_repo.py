import logging
from neo4j import Driver

logger = logging.getLogger(__name__)


def create_connection(driver: Driver, user_id_1: str, user_id_2: str) -> None:
    """
    Create an undirected CONNECTED relationship between two users.
    Uses MERGE so duplicate connections are safely ignored.
    """
    with driver.session() as session:
        session.run(
            """
            MATCH (a:User {id: $u1}), (b:User {id: $u2})
            MERGE (a)-[:CONNECTED]-(b)
            """,
            u1=user_id_1,
            u2=user_id_2,
        )
    logger.info(f"Connection created: {user_id_1} <-> {user_id_2}")


def find_shortest_path(driver: Driver, start_id: str, end_id: str) -> list[str] | None:
    """
    Use Neo4j's native shortestPath() with bidirectional BFS to find
    the shortest path between two users. Returns a list of user IDs
    representing the path, or None if no path exists.
    """
    with driver.session() as session:
        result = session.run(
            """
            MATCH (a:User {id: $start}), (b:User {id: $end})
            MATCH path = shortestPath((a)-[:CONNECTED*]-(b))
            RETURN [node IN nodes(path) | node.id] AS path
            """,
            start=start_id,
            end=end_id,
        )
        record = result.single()
        return record["path"] if record else None


def remove_connection(driver: Driver, user_id_1: str, user_id_2: str) -> None:
    """Delete the CONNECTED relationship between two users if it exists."""
    with driver.session() as session:
        session.run(
            """
            MATCH (a:User {id: $u1})-[r:CONNECTED]-(b:User {id: $u2})
            DELETE r
            """,
            u1=user_id_1,
            u2=user_id_2,
        )
    logger.info(f"Connection removed: {user_id_1} <-> {user_id_2}")


def get_friend_suggestions(driver: Driver, user_id: str) -> list[tuple]:
    """
    Find 'Friends of Friends' (2-hop neighbours) not yet connected to the user.
    Returns a list of (suggested_user_id, mutual_friend_count) tuples,
    sorted by mutual friend count descending.
    """
    with driver.session() as session:
        result = session.run(
            """
            MATCH (u:User {id: $id})-[:CONNECTED]-(friend)-[:CONNECTED]-(fof:User)
            WHERE fof.id <> $id
              AND NOT (u)-[:CONNECTED]-(fof)
            RETURN fof.id AS suggested_user, count(friend) AS mutual_count
            ORDER BY mutual_count DESC
            LIMIT 10
            """,
            id=user_id,
        )
        return [(record["suggested_user"], record["mutual_count"]) for record in result]
