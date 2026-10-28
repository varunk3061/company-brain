
import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

# Load environment variables from the backend .env file.
load_dotenv()

NEO4J_URI = os.getenv(
    "NEO4J_URI",
    "bolt://localhost:7687"
)
NEO4J_USERNAME = os.getenv(
    "NEO4J_USERNAME",
    "neo4j"
)
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv(
    "NEO4J_DATABASE",
    "neo4j"
)

# Create one reusable Neo4j driver.
_driver = None


def get_neo4j_driver():
    """Create the driver only when it is first needed."""
    global _driver

    if _driver is None:
        if not NEO4J_PASSWORD:
            raise RuntimeError(
                "NEO4J_PASSWORD is missing from .env"
            )

        _driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )

    return _driver


def verify_neo4j_connection():
    """Check whether Neo4j is reachable."""
    driver = get_neo4j_driver()

    driver.verify_connectivity()

    with driver.session(
        database=NEO4J_DATABASE
    ) as session:
        result = session.run("RETURN 1 AS status")
        return result.single()["status"] == 1


def close_neo4j_connection():
    """Close the driver during application shutdown."""
    global _driver

    if _driver is not None:
        _driver.close()
        _driver = None


# What does this file do?
# - get_neo4j_driver() creates a reusable connection.
# - verify_neo4j_connection() checks whether Neo4j is working.
# - close_neo4j_connection() releases the connection when the application shuts down.