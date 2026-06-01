from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from neo4j import Driver

from app.core.auth import create_access_token, hash_password, verify_password
from app.db.neo4j_db import get_driver
from app.models.schemas import Token, UserRegister, UserResponse
from app.repositories import user_repo

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=Token,
    status_code=201,
    summary="Register a new user account",
    description=(
        "Creates a new User node in Neo4j with a bcrypt-hashed password. "
        "Returns a JWT access token valid for 24 hours."
    ),
)
def register(user: UserRegister, driver: Driver = Depends(get_driver)):
    existing = user_repo.get_user_by_email(driver, user.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email '{user.email}' is already registered.",
        )
    password_hash = hash_password(user.password)
    created = user_repo.create_user_with_password(
        driver, user.name, user.email, password_hash
    )
    token = create_access_token({"sub": created["id"]})
    return {"access_token": token, "token_type": "bearer"}


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
    form_data: OAuth2PasswordRequestForm = Depends(),
    driver: Driver = Depends(get_driver),
):
    user = user_repo.get_user_by_email(driver, form_data.username)
    if not user or not verify_password(form_data.password, user.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token({"sub": user["id"]})
    return {"access_token": token, "token_type": "bearer"}
