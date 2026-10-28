"""
seed_data.py — Social Network Dataset Ingestion Pipeline.

Supports dataset retrieval from:
  1. AWS S3 (private bucket, IAM authentication)
  2. Local file cache
  3. Stanford SNAP URL (development fallback)

Validates records, tracks metrics, and batch-inserts users and connections
into Neo4j with idempotency.
"""

import logging
import os
import sys
from neo4j import GraphDatabase

# Allow imports from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.services.s3_service import ensure_dataset, parse_and_validate_edges

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("seed_data")

# ─── Configuration ────────────────────────────────────────────────────────────
NEO4J_URI = os.getenv("NEO4J_URI", settings.NEO4J_URI)
NEO4J_USER = os.getenv("NEO4J_USER", settings.NEO4J_USER)
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", settings.NEO4J_PASSWORD)

DATASET_URL = os.getenv(
    "DATASET_URL", "https://snap.stanford.edu/data/facebook_combined.txt.gz"
)
LOCAL_FILE = os.path.join(os.path.dirname(__file__), "facebook_combined.txt.gz")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "500"))
REQUIRE_S3 = os.getenv("REQUIRE_S3", "false").lower() in ("true", "1", "yes")


# ─── Neo4j Batch Insertion Helpers ───────────────────────────────────────────

def _batch_create_users(tx, user_ids: list[str]) -> None:
    tx.run(
        """
        UNWIND $ids AS id
        MERGE (:User {id: id, name: 'User_' + id})
        """,
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


# ─── Ingestion Pipeline ───────────────────────────────────────────────────────

def run_ingestion(
    target_file: str = LOCAL_FILE,
    batch_size: int = BATCH_SIZE,
    clear_existing: bool = True,
    require_s3: bool = REQUIRE_S3,
) -> dict:
    """
    Executes the ingestion pipeline:
      1. Resolves dataset from S3 / Local cache / URL fallback
      2. Validates records and tracks ingestion statistics
      3. Connects to Neo4j and loads nodes & relationships in idempotent batches
    """
    logger.info("Resolving dataset...")
    file_path, source_used = ensure_dataset(
        target_path=target_file,
        bucket=settings.AWS_S3_BUCKET,
        key=settings.AWS_S3_DATASET_KEY,
        fallback_url=DATASET_URL,
        require_s3=require_s3,
    )

    logger.info(f"Dataset ready from '{source_used}' at: {file_path}")

    # Parse and validate records
    logger.info(f"Parsing and validating edge records from: {file_path}")
    parsed = parse_and_validate_edges(file_path)
    stats = parsed["stats"]
    valid_edges = parsed["valid_edges"]
    user_ids = parsed["unique_users"]

    logger.info(
        f"Validation metrics: Total lines={stats['total_lines']} | "
        f"Valid edges={stats['valid_records']} | "
        f"Rejected records={stats['rejected_records']} | "
        f"Unique users={stats['unique_users']}"
    )

    # Neo4j Insertion
    logger.info(f"Connecting to Neo4j at {NEO4J_URI}...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    inserted_users = 0
    inserted_connections = 0

    try:
        driver.verify_connectivity()
        with driver.session() as session:
            if clear_existing:
                logger.info("Clearing existing graph data...")
                session.run("MATCH (n) DETACH DELETE n")

            # Batch insert users
            logger.info(f"Inserting {len(user_ids)} users in batches of {batch_size}...")
            for i in range(0, len(user_ids), batch_size):
                batch = user_ids[i : i + batch_size]
                session.execute_write(_batch_create_users, batch)
                inserted_users += len(batch)

            # Batch insert connections
            logger.info(f"Inserting {len(valid_edges)} connections in batches of {batch_size}...")
            edge_pairs = [[u, v] for u, v in valid_edges]
            for i in range(0, len(edge_pairs), batch_size):
                batch = edge_pairs[i : i + batch_size]
                session.execute_write(_batch_create_connections, batch)
                inserted_connections += len(batch)

        logger.info("Graph ingestion successfully committed.")
    finally:
        driver.close()

    return {
        "status": "success",
        "source_used": source_used,
        "total_lines": stats["total_lines"],
        "valid_edges": stats["valid_records"],
        "rejected_records": stats["rejected_records"],
        "unique_users": stats["unique_users"],
        "inserted_users": inserted_users,
        "inserted_connections": inserted_connections,
    }


if __name__ == "__main__":
    try:
        summary = run_ingestion()
        print("\n=== Ingestion Complete ===")
        for k, v in summary.items():
            print(f"  {k}: {v}")
    except Exception as exc:
        logger.error(f"Ingestion failed: {exc}")
        sys.exit(1)
