# app/db/neo4j_db.py
from neo4j import GraphDatabase
from app.core.config import settings

driver = GraphDatabase.driver(
    settings.NEO4J_URI,
    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
)

def test_connection():
    with driver.session() as session:
        result = session.run("RETURN 1")
        return result.single()[0]