from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from neo4j import Driver

from app.core.security import decode_access_token
from app.db.neo4j_db import get_driver
from app.repositories import user_repo

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def get_current_user(
    token: str = Depends(oauth2_scheme), driver: Driver = Depends(get_driver)
) -> dict:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        claims = decode_access_token(token)
    except jwt.InvalidTokenError:
        raise credentials_error from None
    if not isinstance(claims, dict):
        raise credentials_error
    user_id = claims.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise credentials_error
    if not user_repo.user_exists(driver, user_id):
        raise credentials_error
    return {"user_id": user_id}
