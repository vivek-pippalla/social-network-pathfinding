from fastapi import APIRouter, Depends, Path, Query
from neo4j import Driver

from app.api.deps import get_current_user
from app.db.neo4j_db import get_driver
from app.models.schemas import PathResponse, SuggestionResponse
from app.services import path_service, recommendation_service

router = APIRouter(prefix="/api/v1", tags=["Graph"])
USER_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"


@router.get(
    "/path/{user1}/{user2}",
    response_model=PathResponse,
    summary="Shortest path between two users (protected)",
)
def get_path(
    user1: str = Path(..., pattern=USER_ID_PATTERN),
    user2: str = Path(..., pattern=USER_ID_PATTERN),
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
):
    return path_service.find_path(driver, user1, user2)


@router.get(
    "/suggestions/me",
    response_model=SuggestionResponse,
    summary="Get your own friend suggestions (protected)",
)
def get_my_suggestions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
):
    return recommendation_service.get_suggestions(
        driver, current_user["user_id"], offset=offset, limit=limit
    )


@router.get(
    "/users/{user_id}/suggestions",
    response_model=SuggestionResponse,
    summary="Get friend suggestions for a user (protected)",
)
def get_suggestions(
    user_id: str = Path(..., pattern=USER_ID_PATTERN),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
):
    return recommendation_service.get_suggestions(
        driver, user_id, offset=offset, limit=limit
    )
