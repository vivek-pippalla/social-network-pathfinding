from fastapi import APIRouter, Depends
from neo4j import Driver

from app.api.deps import get_current_user
from app.db.neo4j_db import get_driver
from app.models.schemas import PathResponse, SuggestionResponse
from app.repositories import graph_repo
from app.services import pathfinder

router = APIRouter(prefix="/api/v1", tags=["Graph"])


@router.get(
    "/path/{user1}/{user2}",
    response_model=PathResponse,
    summary="Shortest path between two users (protected)",
)
def get_path(
    user1: str,
    user2: str,
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
):
    return pathfinder.find_shortest_path(driver, user1, user2)


@router.get(
    "/suggestions/me",
    response_model=SuggestionResponse,
    summary="Get your own friend suggestions (protected)",
)
def get_my_suggestions(
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
):
    return pathfinder.get_suggestions(driver, current_user["user_id"])


@router.get(
    "/suggestions/{user_id}",
    response_model=SuggestionResponse,
    summary="Get friend suggestions for a user (protected)",
)
def get_suggestions(
    user_id: str,
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
):
    return pathfinder.get_suggestions(driver, user_id)
