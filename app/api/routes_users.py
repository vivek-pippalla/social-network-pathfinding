from fastapi import APIRouter, Depends, Query, Request
from neo4j import Driver
from redis import Redis

from app.api.deps import get_current_user
from app.db.neo4j_db import get_driver
from app.db.redis_cache import get_client
from app.domain.errors import AppError
from app.models.schemas import OwnProfileResponse, ProfileUpdate, PublicUserResponse
from app.repositories import user_repo
from app.services import auth_service
from app.services import user_service

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.get("/search", response_model=list[PublicUserResponse], summary="Search users by name")
def search_users(
    request: Request,
    q: str = Query(..., min_length=1, max_length=100, description="Search query string"),
    driver: Driver = Depends(get_driver),
    redis_client: Redis = Depends(get_client),
    current_user: dict = Depends(get_current_user),
):
    auth_service.check_search_limit(
        redis_client, request.client.host if request and request.client else "unknown"
    )
    return user_service.search_users(driver, q)


@router.get("/me", response_model=OwnProfileResponse, summary="Get your own profile")
def get_my_profile(
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
):
    profile = user_repo.get_own_profile(driver, current_user["user_id"])
    if not profile:
        raise AppError("USER_NOT_FOUND", "User not found.", 404)
    return profile


@router.put("/me", response_model=OwnProfileResponse, summary="Update your name")
def update_my_profile(
    updates: ProfileUpdate,
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
):
    user_service.update_user(driver, current_user["user_id"], updates.name)
    profile = user_repo.get_own_profile(driver, current_user["user_id"])
    if not profile:
        raise AppError("USER_NOT_FOUND", "User not found.", 404)
    return profile


@router.get("/{user_id}", response_model=PublicUserResponse, summary="Get public user profile")
def get_user(
    user_id: str,
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
):
    return user_service.get_user(driver, user_id)
