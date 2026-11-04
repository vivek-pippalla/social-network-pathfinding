"""Idempotent Neo4j constraints and indexes for the application graph."""

from neo4j import Driver


SCHEMA_STATEMENTS = (
    "CREATE CONSTRAINT user_id_unique IF NOT EXISTS "
    "FOR (u:User) REQUIRE u.id IS UNIQUE",
    "CREATE CONSTRAINT account_email_unique IF NOT EXISTS "
    "FOR (a:Account) REQUIRE a.email_normalized IS UNIQUE",
    "CREATE TEXT INDEX user_name_lower_text IF NOT EXISTS "
    "FOR (u:User) ON (u.name_lower)",
)


def _create_schema(tx) -> None:
    for statement in SCHEMA_STATEMENTS:
        tx.run(statement).consume()


def ensure_schema(driver: Driver) -> None:
    """Create the planned uniqueness constraints and text index if absent."""
    with driver.session() as session:
        session.execute_write(_create_schema)
