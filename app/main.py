from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging_config import setup_logging
from app.db.neo4j_db import get_driver, close_driver
from app.api import routes_users, routes_graph

# Initialise structured logging before anything else
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown events."""
    # Startup: warm up the Neo4j driver (verifies connectivity)
    get_driver()
    yield
    # Shutdown: close the driver gracefully
    close_driver()


app = FastAPI(
    title="Social Network Pathfinding API",
    description=(
        "A production-grade backend that finds shortest connection paths "
        "between users in a social graph, backed by Neo4j and Redis."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(routes_users.router)
app.include_router(routes_graph.router)


@app.get("/health", tags=["Health"], summary="API health check")
async def health_check():
    return {"status": "ok", "message": "Social Network Pathfinding API is running."}
