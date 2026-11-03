"""Neo4j transactions used by the dataset ingestion service."""

from neo4j import Driver, Query

from app.core.config import settings
from app.repositories.graph_repo import canonical_pair


def delete_snap_data(driver: Driver) -> tuple[int, int]:
    query = Query(
        "MATCH (u:User {source: 'snap'}) DETACH DELETE u",
        timeout=settings.NEO4J_QUERY_TIMEOUT_SECONDS,
    )
    with driver.session() as session:
        summary = session.execute_write(lambda tx: tx.run(query).consume())
    return summary.counters.nodes_deleted, summary.counters.relationships_deleted


def delete_all_data(driver: Driver) -> tuple[int, int]:
    query = Query(
        "MATCH (n) DETACH DELETE n", timeout=settings.NEO4J_QUERY_TIMEOUT_SECONDS
    )
    with driver.session() as session:
        summary = session.execute_write(lambda tx: tx.run(query).consume())
    return summary.counters.nodes_deleted, summary.counters.relationships_deleted


def merge_snap_users(driver: Driver, user_ids: list[str]) -> int:
    rows = [
        {"id": user_id, "name": f"User_{user_id}", "name_lower": f"user_{user_id}"}
        for user_id in user_ids
    ]
    query = Query(
        """
        UNWIND $users AS row
        MERGE (u:User {id: row.id})
        ON CREATE SET u.name = row.name,
                      u.name_lower = row.name_lower,
                      u.source = 'snap',
                      u.created_at = datetime()
        """,
        timeout=settings.NEO4J_QUERY_TIMEOUT_SECONDS,
    )
    with driver.session() as session:
        summary = session.execute_write(lambda tx: tx.run(query, users=rows).consume())
    return summary.counters.nodes_created


def merge_snap_edges(driver: Driver, edges: list[tuple[str, str]]) -> int:
    rows = [
        {"low_id": low_id, "high_id": high_id}
        for low_id, high_id in (canonical_pair(a, b) for a, b in edges)
    ]
    query = Query(
        """
        UNWIND $edges AS edge
        MATCH (lo:User {id: edge.low_id}), (hi:User {id: edge.high_id})
        MERGE (lo)-[:CONNECTED]->(hi)
        """,
        timeout=settings.NEO4J_QUERY_TIMEOUT_SECONDS,
    )
    with driver.session() as session:
        summary = session.execute_write(lambda tx: tx.run(query, edges=rows).consume())
    return summary.counters.relationships_created


def snap_graph_counts(driver: Driver) -> tuple[int, int]:
    query = Query(
        """
        MATCH (u:User {source: 'snap'})
        WITH count(u) AS users
        OPTIONAL MATCH (a:User {source: 'snap'})-[r:CONNECTED]->(b:User {source: 'snap'})
        RETURN users, count(r) AS relationships
        """,
        timeout=settings.NEO4J_QUERY_TIMEOUT_SECONDS,
    )
    with driver.session() as session:
        record = session.execute_read(lambda tx: tx.run(query).single())
    return record["users"], record["relationships"]


def random_snap_user_ids(driver: Driver, limit: int) -> list[str]:
    query = Query(
        """
        MATCH (u:User {source: 'snap'})
        RETURN u.id AS id
        ORDER BY rand()
        LIMIT $limit
        """,
        timeout=settings.NEO4J_QUERY_TIMEOUT_SECONDS,
    )
    with driver.session() as session:
        records = session.execute_read(lambda tx: list(tx.run(query, limit=limit)))
    return [record["id"] for record in records]
