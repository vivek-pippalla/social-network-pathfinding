from fastapi import APIRouter, Depends, HTTPException, status
from neo4j import Driver

from app.core.auth import get_current_user
from app.db.neo4j_db import get_driver
from app.models.schemas import ConnectionResponse
from app.repositories import graph_repo, user_repo

router = APIRouter(prefix="/friends", tags=["Friends"])


@router.post(
    "/{friend_id}",
    response_model=ConnectionResponse,
    status_code=201,
    summary="Add a friend connection (protected)",
)
def add_friend(
    friend_id: str,
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
):
    me = current_user["user_id"]
    if me == friend_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot add yourself.")
    if not user_repo.get_user_by_id(driver, friend_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{friend_id}' not found.")
    graph_repo.create_connection(driver, me, friend_id)
    return {"message": f"You are now connected with user '{friend_id}'."}


@router.delete(
    "/{friend_id}",
    response_model=ConnectionResponse,
    summary="Remove a friend connection (protected)",
)
def remove_friend(
    friend_id: str,
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
):
    me = current_user["user_id"]
    if me == friend_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot remove yourself.")
    graph_repo.remove_connection(driver, me, friend_id)
    return {"message": f"Connection with user '{friend_id}' removed."}
