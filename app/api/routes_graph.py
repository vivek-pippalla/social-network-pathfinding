from fastapi import APIRouter, Depends
from neo4j import Driver
from app.db.neo4j_db import get_driver
from app.models.schemas import ConnectionCreate, ConnectionResponse, PathResponse, SuggestionResponse
from app.repositories import graph_repo
from app.services import pathfinder

router = APIRouter(prefix="/api/v1", tags=["Graph"])


@router.post(
    "/connections",
    response_model=ConnectionResponse,
    status_code=201,
    summary="Create a connection between two users",
)
def create_connection(conn: ConnectionCreate, driver: Driver = Depends(get_driver)):
    graph_repo.create_connection(driver, conn.user_id_1, conn.user_id_2)
    return {"message": f"Connection between '{conn.user_id_1}' and '{conn.user_id_2}' created."}


@router.get(
    "/path/{start_user}/{end_user}",
    response_model=PathResponse,
    summary="Find the shortest path between two users",
)
def get_shortest_path(start_user: str, end_user: str, driver: Driver = Depends(get_driver)):
    """
    Returns the shortest connection path between two users.
    - First call: queries Neo4j (may take ~50–200ms).
    - Subsequent calls: returned from Redis cache (~5ms).
    The `cached` field in the response tells you which happened.
    """
    return pathfinder.find_shortest_path(driver, start_user, end_user)


@router.get(
    "/suggestions/{user_id}",
    response_model=SuggestionResponse,
    summary="Get friend suggestions for a user",
)
def get_suggestions(user_id: str, driver: Driver = Depends(get_driver)):
    """
    Returns up to 10 'People You May Know' suggestions based on mutual friends.
    Ranked by mutual friend count.
    """
    return pathfinder.get_suggestions(driver, user_id)
