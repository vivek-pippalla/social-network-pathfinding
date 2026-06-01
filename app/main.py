from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.logging_config import setup_logging
from app.db.neo4j_db import get_driver, close_driver
from app.api import routes_users, routes_graph, routes_auth, routes_friends

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_driver()
    yield
    close_driver()


app = FastAPI(
    title="Social Network Pathfinding API",
    description=(
        "A production-grade social graph API backed by Neo4j and Redis.\n\n"
        "**Public:** `/distance`, `/suggestions/{user_id}`, `/profile/{user_id}`\n\n"
        "**Protected:** Register at `/api/v1/auth/register`, click **Authorize** above, "
        "then access `/suggestions/me`, `/profile/me`, `/friends/{friend_id}`."
    ),
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# route order matters: graph router registers /suggestions/me before /suggestions/{user_id}
app.include_router(routes_auth.router)
app.include_router(routes_graph.router)
app.include_router(routes_users.router)
app.include_router(routes_friends.router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

Instrumentator().instrument(app).expose(app, include_in_schema=False)


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/health", tags=["Health"], summary="API health check")
async def health_check():
    return {"status": "ok", "message": "Social Network Pathfinding API is running."}
