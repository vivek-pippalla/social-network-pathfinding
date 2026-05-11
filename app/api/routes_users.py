from fastapi import APIRouter, Depends
from neo4j import Driver
from app.db.neo4j_db import get_driver
from app.models.schemas import UserCreate, UserResponse
from app.services import user_service

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.post("/", response_model=UserResponse, status_code=201, summary="Create a new user")
def create_user(user: UserCreate, driver: Driver = Depends(get_driver)):
    return user_service.create_user(driver, user)


@router.get("/search", response_model=list[UserResponse], summary="Search users by name")
def search_users(q: str, driver: Driver = Depends(get_driver)):
    return user_service.search_users(driver, q)


@router.get("/{user_id}", response_model=UserResponse, summary="Get a user by ID")
def get_user(user_id: str, driver: Driver = Depends(get_driver)):
    return user_service.get_user(driver, user_id)
