from fastapi import APIRouter, Depends, Path, Query
from neo4j import Driver

from app.api.deps import get_cache_service, get_current_user
from app.api.openapi import route_errors
from app.db.neo4j_db import get_driver
from app.models.schemas import PathResponse, SuggestionResponse
from app.services import path_service, recommendation_service
from app.services.cache_service import CacheService

router = APIRouter(prefix="/api/v1", tags=["Graph"])
USER_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"


@router.get(
    "/path/{a}/{b}",
    response_model=PathResponse,
    summary="Shortest path between two users (protected)",
    operation_id="getShortestPath",
    responses=route_errors("USER_NOT_FOUND", "PATH_NOT_FOUND", protected=True),
)
def get_path(
    a: str = Path(..., pattern=USER_ID_PATTERN, description="Starting user ID"),
    b: str = Path(..., pattern=USER_ID_PATTERN, description="Ending user ID"),
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
    cache: CacheService = Depends(get_cache_service),
):
    return path_service.find_path(driver, a, b, cache)


@router.get(
    "/suggestions/me",
    response_model=SuggestionResponse,
    summary="Get your own friend suggestions (protected)",
    operation_id="getMySuggestions",
    responses=route_errors("USER_NOT_FOUND", protected=True),
)
def get_my_suggestions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
):
    result = recommendation_service.get_suggestions(
        driver, current_user["user_id"], offset=offset, limit=limit
    )
    return {
        "items": result["suggestions"],
        "limit": result["limit"],
        "offset": result["offset"],
        "total": None,
    }


@router.get(
    "/users/{id}/suggestions",
    response_model=SuggestionResponse,
    summary="Get friend suggestions for a user (protected)",
    operation_id="getUserSuggestions",
    responses=route_errors("USER_NOT_FOUND", protected=True),
)
def get_suggestions(
    id: str = Path(..., pattern=USER_ID_PATTERN),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
):
    result = recommendation_service.get_suggestions(
        driver, id, offset=offset, limit=limit
    )
    return {
        "items": result["suggestions"],
        "limit": result["limit"],
        "offset": result["offset"],
        "total": None,
    }
