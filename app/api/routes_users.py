from fastapi import APIRouter, Depends, Path, Query, Request
from neo4j import Driver
from redis import Redis

from app.api.deps import get_current_user
from app.api.openapi import route_errors
from app.db.neo4j_db import get_driver
from app.db.redis_cache import get_client
from app.models.schemas import (
    OwnProfileResponse,
    PaginationPage,
    ProfileUpdate,
    PublicUserResponse,
)
from app.services import auth_service
from app.services import user_service

router = APIRouter(prefix="/api/v1/users", tags=["Users"])
USER_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"


@router.get(
    "/search",
    response_model=PaginationPage[PublicUserResponse],
    summary="Search users by name",
    operation_id="searchUsers",
    responses=route_errors("RATE_LIMITED", protected=True),
)
def search_users(
    request: Request,
    q: str = Query(
        ..., min_length=2, max_length=100, description="Search query string"
    ),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    driver: Driver = Depends(get_driver),
    redis_client: Redis = Depends(get_client),
    current_user: dict = Depends(get_current_user),
):
    auth_service.check_search_limit(
        redis_client, request.client.host if request and request.client else "unknown"
    )
    items = user_service.search_users(driver, q, offset=offset, limit=limit)
    return {"items": items, "limit": limit, "offset": offset, "total": None}


@router.get(
    "/me",
    response_model=OwnProfileResponse,
    summary="Get your own profile",
    operation_id="getOwnProfile",
    responses=route_errors("USER_NOT_FOUND", protected=True),
)
def get_my_profile(
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
):
    return user_service.get_own_profile(driver, current_user["user_id"])


@router.put(
    "/me",
    response_model=OwnProfileResponse,
    summary="Update your name",
    operation_id="updateOwnProfile",
    responses=route_errors("USER_NOT_FOUND", protected=True),
)
def update_my_profile(
    updates: ProfileUpdate,
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
):
    return user_service.update_own_profile(
        driver, current_user["user_id"], updates.name
    )


@router.get(
    "/{id}",
    response_model=PublicUserResponse,
    summary="Get public user profile",
    operation_id="getPublicProfile",
    responses=route_errors("USER_NOT_FOUND", protected=True),
)
def get_user(
    id: str = Path(..., pattern=USER_ID_PATTERN),
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
):
    return user_service.get_user(driver, id)
