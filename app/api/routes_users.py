from fastapi import APIRouter, Depends, Path, Query, Request
from neo4j import Driver
from redis import Redis

from app.api.deps import get_current_user
from app.db.neo4j_db import get_driver
from app.db.redis_cache import get_client
from app.models.schemas import OwnProfileResponse, ProfileUpdate, PublicUserResponse
from app.services import auth_service
from app.services import user_service

router = APIRouter(prefix="/api/v1/users", tags=["Users"])
USER_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"


@router.get(
    "/search", response_model=list[PublicUserResponse], summary="Search users by name"
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
    return user_service.search_users(driver, q, offset=offset, limit=limit)


@router.get("/me", response_model=OwnProfileResponse, summary="Get your own profile")
def get_my_profile(
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
):
    return user_service.get_own_profile(driver, current_user["user_id"])


@router.put("/me", response_model=OwnProfileResponse, summary="Update your name")
def update_my_profile(
    updates: ProfileUpdate,
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
):
    return user_service.update_own_profile(
        driver, current_user["user_id"], updates.name
    )


@router.get(
    "/{user_id}", response_model=PublicUserResponse, summary="Get public user profile"
)
def get_user(
    user_id: str = Path(..., pattern=USER_ID_PATTERN),
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
):
    return user_service.get_user(driver, user_id)
