from neo4j import Driver

from app.db.neo4j_db import with_transaction_timeout
from app.core.metrics import observe_neo4j_query


@observe_neo4j_query("user.get_by_id")
def get_user_by_id(driver: Driver, user_id: str) -> dict | None:
    query = """
        MATCH (u:User {id: $id})
        RETURN u.id AS id, u.name AS name, coalesce(u.source, 'snap') AS source
    """
    with driver.session() as session:
        record = session.execute_read(
            with_transaction_timeout(lambda tx: tx.run(query, id=user_id).single())
        )
    return dict(record) if record else None


@observe_neo4j_query("user.get_own_profile")
def get_own_profile(driver: Driver, user_id: str) -> dict | None:
    query = """
        MATCH (a:Account)-[:OWNS]->(u:User {id: $id})
        RETURN u.id AS id, u.name AS name,
               coalesce(u.source, 'app') AS source, a.email AS email
    """
    with driver.session() as session:
        record = session.execute_read(
            with_transaction_timeout(lambda tx: tx.run(query, id=user_id).single())
        )
    return dict(record) if record else None


@observe_neo4j_query("user.exists")
def user_exists(driver: Driver, user_id: str) -> bool:
    query = "MATCH (u:User {id: $id}) RETURN u.id AS id"
    with driver.session() as session:
        record = session.execute_read(
            with_transaction_timeout(lambda tx: tx.run(query, id=user_id).single())
        )
    return record is not None


@observe_neo4j_query("user.update")
def update_user(driver: Driver, user_id: str, name: str) -> dict | None:
    query = """
        MATCH (u:User {id: $id})
        SET u.name = $name, u.name_lower = toLower($name)
        RETURN u.id AS id, u.name AS name,
               coalesce(u.source, 'snap') AS source
    """
    with driver.session() as session:
        record = session.execute_write(
            with_transaction_timeout(
                lambda tx: tx.run(query, id=user_id, name=name).single()
            )
        )
    return dict(record) if record else None


@observe_neo4j_query("user.search")
def search_users(
    driver: Driver, query: str, offset: int = 0, limit: int = 20
) -> list[dict]:
    """Search normalized names through the Neo4j text index."""
    cypher = """
        MATCH (u:User)
        WHERE u.name_lower CONTAINS $q_lower
        RETURN u.id AS id, u.name AS name,
               coalesce(u.source, 'snap') AS source
        ORDER BY u.name, u.id
        SKIP $offset LIMIT $limit
    """
    with driver.session() as session:
        records = session.execute_read(
            with_transaction_timeout(
                lambda tx: list(
                    tx.run(
                        cypher,
                        q_lower=query.strip().lower(),
                        offset=offset,
                        limit=limit,
                    )
                )
            )
        )
    return [dict(record) for record in records]
