from neo4j import Driver, Query

from app.core.config import settings


def get_users_by_ids(driver: Driver, user_ids: list[str]) -> dict[str, dict]:
    """Return public User projections for the requested IDs in one read tx."""
    with driver.session() as session:
        records = session.execute_read(
            lambda tx: list(
                tx.run(
                    Query(
                        """
                        MATCH (u:User)
                        WHERE u.id IN $user_ids
                        RETURN u.id AS id, u.name AS name
                        """,
                        timeout=settings.NEO4J_QUERY_TIMEOUT_SECONDS,
                    ),
                    user_ids=user_ids,
                )
            )
        )
    return {record["id"]: dict(record) for record in records}


def find_bounded_shortest_path(
    driver: Driver, start_id: str, end_id: str, max_depth: int
) -> list[dict] | None:
    """Find a shortest path no longer than max_depth, including public names."""
    if isinstance(max_depth, bool) or not isinstance(max_depth, int) or max_depth < 1:
        raise ValueError("max_depth must be a positive integer")
    depth = int(max_depth)
    query = Query(
        f"""
        MATCH (a:User {{id: $start_id}}), (b:User {{id: $end_id}})
        MATCH path = shortestPath((a)-[:CONNECTED*..{depth}]-(b))
        RETURN [node IN nodes(path) | {{id: node.id, name: node.name}}] AS path
        """,
        timeout=settings.NEO4J_QUERY_TIMEOUT_SECONDS,
    )
    with driver.session() as session:
        record = session.execute_read(
            lambda tx: tx.run(query, start_id=start_id, end_id=end_id).single()
        )
    return record["path"] if record else None


def get_recommendations(
    driver: Driver, user_id: str, offset: int = 0, limit: int = 20
) -> list[dict]:
    """Return paged friend-of-friend candidates with distinct mutual counts."""
    query = Query(
        """
        MATCH (u:User {id: $user_id})-[:CONNECTED]-(friend:User)-[:CONNECTED]-(candidate:User)
        WHERE candidate <> u AND NOT (u)-[:CONNECTED]-(candidate)
        RETURN candidate.id AS user_id, candidate.name AS name,
               count(DISTINCT friend) AS mutual_friends
        ORDER BY mutual_friends DESC, user_id ASC
        SKIP $offset LIMIT $limit
        """,
        timeout=settings.NEO4J_QUERY_TIMEOUT_SECONDS,
    )
    with driver.session() as session:
        records = session.execute_read(
            lambda tx: list(
                tx.run(
                    query,
                    user_id=user_id,
                    offset=offset,
                    limit=limit,
                )
            )
        )
    return [dict(record) for record in records]


def canonical_pair(user_id_1: str, user_id_2: str) -> tuple[str, str]:
    """Return the one stored ordering for an undirected friendship."""
    return tuple(sorted((user_id_1, user_id_2)))


def _add_friendship(tx, low_id: str, high_id: str, timeout: float):
    result = tx.run(
        Query(
            """
        MATCH (lo:User {id: $low_id}), (hi:User {id: $high_id})
        MERGE (lo)-[r:CONNECTED]->(hi)
        ON CREATE SET r.created_at = datetime()
        RETURN lo.id AS low_id, hi.id AS high_id
        """,
            timeout=timeout,
        ),
        low_id=low_id,
        high_id=high_id,
    )
    record = result.single()
    summary = result.consume()
    if record is None:
        return None, False
    return dict(record), summary.counters.relationships_created > 0


def add_friendship(driver: Driver, user_id_1: str, user_id_2: str) -> tuple[bool, bool]:
    low_id, high_id = canonical_pair(user_id_1, user_id_2)
    with driver.session() as session:
        record, changed = session.execute_write(
            _add_friendship,
            low_id,
            high_id,
            settings.NEO4J_QUERY_TIMEOUT_SECONDS,
        )
    return record is not None, changed


def _remove_friendship(tx, low_id: str, high_id: str, timeout: float):
    result = tx.run(
        Query(
            """
        MATCH (lo:User {id: $low_id}), (hi:User {id: $high_id})
        OPTIONAL MATCH (lo)-[r:CONNECTED]-(hi)
        WITH lo, hi, collect(r) AS relationships
        FOREACH (relationship IN relationships | DELETE relationship)
        RETURN lo.id AS low_id, hi.id AS high_id
        """,
            timeout=timeout,
        ),
        low_id=low_id,
        high_id=high_id,
    )
    record = result.single()
    summary = result.consume()
    if record is None:
        return None, False
    return dict(record), summary.counters.relationships_deleted > 0


def remove_friendship(
    driver: Driver, user_id_1: str, user_id_2: str
) -> tuple[bool, bool]:
    low_id, high_id = canonical_pair(user_id_1, user_id_2)
    with driver.session() as session:
        record, changed = session.execute_write(
            _remove_friendship,
            low_id,
            high_id,
            settings.NEO4J_QUERY_TIMEOUT_SECONDS,
        )
    return record is not None, changed


def _list_friends(tx, user_id: str, offset: int, limit: int, timeout: float):
    result = tx.run(
        Query(
            """
        MATCH (u:User {id: $user_id})-[:CONNECTED]-(friend:User)
        RETURN friend.id AS id, friend.name AS name,
               coalesce(friend.source, 'snap') AS source
        ORDER BY friend.name, friend.id
        SKIP $offset LIMIT $limit
        """,
            timeout=timeout,
        ),
        user_id=user_id,
        offset=offset,
        limit=limit,
    )
    return [dict(record) for record in result]


def list_friends(
    driver: Driver, user_id: str, offset: int = 0, limit: int = 20
) -> list[dict]:
    with driver.session() as session:
        return session.execute_read(
            _list_friends,
            user_id,
            offset,
            limit,
            settings.NEO4J_QUERY_TIMEOUT_SECONDS,
        )


def _mutual_friends(
    tx, user_id_1: str, user_id_2: str, offset: int, limit: int, timeout: float
):
    result = tx.run(
        Query(
            """
        MATCH (a:User {id: $user_id_1})-[:CONNECTED]-(mutual:User)-[:CONNECTED]-(b:User {id: $user_id_2})
        RETURN DISTINCT mutual.id AS id, mutual.name AS name,
               coalesce(mutual.source, 'snap') AS source
        ORDER BY mutual.name, mutual.id
        SKIP $offset LIMIT $limit
        """,
            timeout=timeout,
        ),
        user_id_1=user_id_1,
        user_id_2=user_id_2,
        offset=offset,
        limit=limit,
    )
    return [dict(record) for record in result]


def mutual_friends(
    driver: Driver, user_id_1: str, user_id_2: str, offset: int = 0, limit: int = 20
) -> list[dict]:
    with driver.session() as session:
        return session.execute_read(
            _mutual_friends,
            user_id_1,
            user_id_2,
            offset,
            limit,
            settings.NEO4J_QUERY_TIMEOUT_SECONDS,
        )
