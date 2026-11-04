import pytest
from neo4j.exceptions import ConstraintError

from app.db.schema import ensure_schema


pytestmark = pytest.mark.integration


def test_schema_bootstrap_is_idempotent(clean_graph):
    driver, _ = clean_graph
    ensure_schema(driver)
    ensure_schema(driver)
    with driver.session() as session:
        names = {
            record["name"]
            for record in session.run("SHOW CONSTRAINTS YIELD name RETURN name")
        }
        index_names = {
            record["name"]
            for record in session.run("SHOW INDEXES YIELD name RETURN name")
        }
    assert {"user_id_unique", "account_email_unique"} <= names
    assert "user_name_lower_text" in index_names


@pytest.mark.parametrize(
    "label,property_name,value",
    [
        ("User", "id", "same-user"),
        ("Account", "email_normalized", "same@example.test"),
    ],
)
def test_unique_constraints_reject_duplicates(clean_graph, label, property_name, value):
    driver, _ = clean_graph
    query = f"CREATE (n:{label} {{{property_name}: $value}}) RETURN n"
    with driver.session() as session:
        session.run(query, value=value).consume()
        with pytest.raises(ConstraintError):
            session.run(query, value=value).consume()


def test_user_id_lookup_uses_unique_index_seek(clean_graph):
    driver, _ = clean_graph
    with driver.session() as session:
        summary = session.run(
            "EXPLAIN MATCH (u:User {id: $id}) RETURN u", id="x"
        ).consume()

    def operator_types(plan):
        yield plan["operatorType"]
        for child in plan.get("children", []):
            yield from operator_types(child)

    assert any("UniqueIndexSeek" in op for op in operator_types(summary.plan))


def test_user_name_text_index_exists(clean_graph):
    driver, _ = clean_graph
    with driver.session() as session:
        indexes = list(
            session.run(
                "SHOW INDEXES YIELD name, type, entityType "
                "WHERE name = $name RETURN name, type, entityType",
                name="user_name_lower_text",
            )
        )
    assert len(indexes) == 1
    assert indexes[0]["type"] == "TEXT"
    assert indexes[0]["entityType"] == "NODE"
