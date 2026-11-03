from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from neo4j import Driver
from redis import Redis

from app.db.redis_cache import get_client
from app.db.neo4j_db import get_driver
from app.models.schemas import Token, UserRegister
from app.services import auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=Token,
    status_code=201,
    summary="Register a new user account",
    description="Create a user and private account, then return a 30-minute access token.",
)
def register(
    user: UserRegister,
    request: Request,
    driver: Driver = Depends(get_driver),
    redis_client: Redis = Depends(get_client),
):
    return auth_service.register(
        driver,
        redis_client,
        client_ip=request.client.host if request.client else "unknown",
        name=user.name,
        email=str(user.email),
        password=user.password,
    )


@router.post(
    "/token",
    response_model=Token,
    summary="Login and get a JWT token",
    description=(
        "Standard OAuth2 password flow. Submit **email** as `username` and your password. "
        "The Swagger UI 'Authorize' button uses this endpoint automatically."
    ),
)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    driver: Driver = Depends(get_driver),
    redis_client: Redis = Depends(get_client),
):
    return auth_service.login(
        driver,
        redis_client,
        client_ip=request.client.host if request.client else "unknown",
        email=form_data.username,
        password=form_data.password,
    )
