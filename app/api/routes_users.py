from fastapi import APIRouter, Depends, HTTPException, status
from neo4j import Driver

from app.core.auth import get_current_user
from app.db.neo4j_db import get_driver
from app.models.schemas import ProfileUpdate, UserResponse
from app.services import user_service

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("/me", response_model=UserResponse, summary="Get your own profile (protected)")
def get_my_profile(
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
):
    return user_service.get_user(driver, current_user["user_id"])


@router.put("/me", response_model=UserResponse, summary="Update your profile (protected)")
def update_my_profile(
    updates: ProfileUpdate,
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
):
    if not updates.name and not updates.email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide at least one field to update (name or email).",
        )
    return user_service.update_user(driver, current_user["user_id"], updates.name, updates.email)


@router.get("/search", response_model=list[UserResponse], summary="Search users by name (public)")
def search_users(q: str, driver: Driver = Depends(get_driver)):
    return user_service.search_users(driver, q)


@router.get("/{user_id}", response_model=UserResponse, summary="Get any user's public profile")
def get_profile(user_id: str, driver: Driver = Depends(get_driver)):
    return user_service.get_user(driver, user_id)
