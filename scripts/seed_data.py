import random
from neo4j import GraphDatabase

URI = "bolt://localhost:7687"
USER = "neo4j"
PASSWORD = "password"

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

NUM_USERS = 100
MAX_CONNECTIONS = 5

def create_users(tx, user_id):
    tx.run("CREATE (:User {id: $id})", id=user_id)

def create_connection(tx, u1, u2):
    tx.run("""
        MATCH (a:User {id: $u1}), (b:User {id: $u2})
        MERGE (a)-[:CONNECTED]->(b)
    """, u1=u1, u2=u2)

with driver.session() as session:
    # Create users
    for i in range(NUM_USERS):
        session.write_transaction(create_users, f"user_{i}")
    # Create random connections
    for i in range(NUM_USERS):
        for _ in range(random.randint(1, MAX_CONNECTIONS)):
            target = random.randint(0, NUM_USERS - 1)
            if target != i:
                session.write_transaction(create_connection, f"user_{i}", f"user_{target}")

print("✅ Data seeding complete")