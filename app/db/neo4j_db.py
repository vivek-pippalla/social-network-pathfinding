import logging
from neo4j import GraphDatabase, Driver
from app.core.config import settings

logger = logging.getLogger(__name__)

# Singleton driver instance — Neo4j manages a connection pool internally.
_driver: Driver = None


def get_driver() -> Driver:
    """
    Returns the singleton Neo4j driver.
    Used as a FastAPI dependency: Depends(get_driver).
    """
    global _driver
    if _driver is None:
        logger.info("Initialising Neo4j driver...")
        _driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
        _driver.verify_connectivity()
        logger.info("Neo4j driver ready.")
    return _driver


def close_driver() -> None:
    """Gracefully close the driver on application shutdown."""
    global _driver
    if _driver:
        _driver.close()
        _driver = None
        logger.info("Neo4j driver closed.")