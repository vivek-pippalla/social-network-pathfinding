"""
seed_data.py — Stanford SNAP Facebook Social Network Dataset Ingestion

Dataset:  Facebook Social Circles (ego-Facebook)
Source:   https://snap.stanford.edu/data/ego-Facebook.html
Size:     4,039 users | 88,234 connections

Usage:
    # Ensure Neo4j is running, then:
    python scripts/seed_data.py

The script will:
  1. Download the dataset from Stanford SNAP (once, ~1 MB).
  2. Parse the edge list.
  3. Clear any existing data from Neo4j.
  4. Batch-insert all users and connections efficiently.
"""

import gzip
import os
import urllib.request
from neo4j import GraphDatabase

# ─── Config ──────────────────────────────────────────────────────────────────
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")

DATASET_URL = "https://snap.stanford.edu/data/facebook_combined.txt.gz"
LOCAL_FILE = os.path.join(os.path.dirname(__file__), "facebook_combined.txt.gz")

BATCH_SIZE = 500  # Number of records per Neo4j transaction

# ─── Download ────────────────────────────────────────────────────────────────

def download_dataset() -> None:
    if os.path.exists(LOCAL_FILE):
        print("📁 Dataset already downloaded — skipping.")
        return
    print("📥 Downloading Facebook Social Network dataset from Stanford SNAP...")
    urllib.request.urlretrieve(DATASET_URL, LOCAL_FILE)
    print("✅ Download complete.")


# ─── Parse ───────────────────────────────────────────────────────────────────

def parse_edges() -> list[tuple[str, str]]:
    """Read the gzipped edge list and return a list of (user_id, user_id) tuples."""
    edges = []
    with gzip.open(LOCAL_FILE, "rt") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            u, v = line.split()
            edges.append((u, v))
    return edges


# ─── Neo4j helpers ───────────────────────────────────────────────────────────

def _batch_create_users(tx, user_ids: list[str]) -> None:
    tx.run(
        "UNWIND $ids AS id MERGE (:User {id: id, name: 'User_' + id})",
        ids=user_ids,
    )


def _batch_create_connections(tx, edges: list[list[str]]) -> None:
    tx.run(
        """
        UNWIND $edges AS edge
        MATCH (a:User {id: edge[0]}), (b:User {id: edge[1]})
        MERGE (a)-[:CONNECTED]-(b)
        """,
        edges=edges,
    )


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    download_dataset()

    edges = parse_edges()
    user_ids = list({uid for edge in edges for uid in edge})

    print(f"👥 Unique users  : {len(user_ids):,}")
    print(f"🔗 Connections   : {len(edges):,}")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    with driver.session() as session:
        # Clear existing graph data
        print("\n🗑️  Clearing existing data...")
        session.run("MATCH (n) DETACH DELETE n")

        # ── Insert users in batches ──
        print("⚙️  Inserting users...")
        for i in range(0, len(user_ids), BATCH_SIZE):
            batch = user_ids[i : i + BATCH_SIZE]
            session.execute_write(_batch_create_users, batch)
            print(f"   Users: {min(i + BATCH_SIZE, len(user_ids)):,} / {len(user_ids):,}", end="\r")
        print(f"\n✅ All {len(user_ids):,} users created.")

        # ── Insert connections in batches ──
        print("⚙️  Inserting connections...")
        edge_pairs = [[u, v] for u, v in edges]
        for i in range(0, len(edge_pairs), BATCH_SIZE):
            batch = edge_pairs[i : i + BATCH_SIZE]
            session.execute_write(_batch_create_connections, batch)
            print(f"   Connections: {min(i + BATCH_SIZE, len(edge_pairs)):,} / {len(edge_pairs):,}", end="\r")
        print(f"\n✅ All {len(edge_pairs):,} connections created.")

    driver.close()
    print("\n🎉 Seeding complete! Neo4j is ready.")


if __name__ == "__main__":
    main()