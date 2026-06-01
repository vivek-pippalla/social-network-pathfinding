from fastapi import APIRouter, Depends
from neo4j import Driver

from app.core.auth import get_current_user
from app.db.neo4j_db import get_driver
from app.models.schemas import PathResponse, SuggestionResponse
from app.services import pathfinder

router = APIRouter(tags=["Graph"])


@router.get(
    "/suggestions/me",
    response_model=SuggestionResponse,
    summary="Get personalized friend suggestions (protected)",
    description="Uses the JWT to identify you and returns ranked friend-of-friend suggestions.",
)
def get_my_suggestions(
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
):
    return pathfinder.get_suggestions(driver, current_user["user_id"])


@router.get(
    "/suggestions/{user_id}",
    response_model=SuggestionResponse,
    summary="Get friend suggestions for any user (public)",
    description="Returns 2-hop friends-of-friends ranked by mutual friend count.",
)
def get_suggestions(
    user_id: str,
    driver: Driver = Depends(get_driver),
):
    return pathfinder.get_suggestions(driver, user_id)


@router.get(
    "/distance/{user1}/{user2}",
    response_model=PathResponse,
    summary="Shortest path between two users (public)",
    description=(
        "Bidirectional BFS via Neo4j shortestPath. Results cached in Redis. "
        "Try 0 → 1000 then run again to see a cache hit."
    ),
)
def get_distance(
    user1: str,
    user2: str,
    driver: Driver = Depends(get_driver),
):
    return pathfinder.find_shortest_path(driver, user1, user2)
