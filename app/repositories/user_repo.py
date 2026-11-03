from neo4j import Driver


def get_user_by_id(driver: Driver, user_id: str) -> dict | None:
    """Fetch a single User node by its id. Returns None if not found."""
    with driver.session() as session:
        record = session.execute_read(
            lambda tx: tx.run(
                """
                MATCH (u:User {id: $id})
                RETURN u.id AS id, u.name AS name, coalesce(u.source, 'snap') AS source
                """,
                id=user_id,
            ).single()
        )
    return dict(record) if record else None


def get_own_profile(driver: Driver, user_id: str) -> dict | None:
    with driver.session() as session:
        record = session.execute_read(
            lambda tx: tx.run(
                """
                MATCH (a:Account)-[:OWNS]->(u:User {id: $id})
                RETURN u.id AS id, u.name AS name,
                       coalesce(u.source, 'app') AS source, a.email AS email
                """,
                id=user_id,
            ).single()
        )
    return dict(record) if record else None


def user_exists(driver: Driver, user_id: str) -> bool:
    with driver.session() as session:
        record = session.execute_read(
            lambda tx: tx.run(
                "MATCH (u:User {id: $id}) RETURN u.id AS id", id=user_id
            ).single()
        )
    return record is not None


def update_user(driver: Driver, user_id: str, name: str) -> dict | None:
    with driver.session() as session:
        record = session.execute_write(
            lambda tx: tx.run(
                """
                MATCH (u:User {id: $id})
                SET u.name = $name, u.name_lower = toLower($name)
                RETURN u.id AS id, u.name AS name,
                       coalesce(u.source, 'snap') AS source
                """,
                id=user_id,
                name=name,
            ).single()
        )
    return dict(record) if record else None


def search_users(driver: Driver, query: str) -> list[dict]:
    """Case-insensitive name search. Returns up to 20 results."""
    with driver.session() as session:
        records = session.execute_read(
            lambda tx: list(
                tx.run(
                    """
                    MATCH (u:User)
                    WHERE toLower(u.name) CONTAINS toLower($q)
                    RETURN u.id AS id, u.name AS name,
                           coalesce(u.source, 'snap') AS source
                    ORDER BY u.name, u.id
                    LIMIT 20
                    """,
                    q=query,
                )
            )
        )
    return [dict(record) for record in records]
