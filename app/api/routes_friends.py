from fastapi import APIRouter, Depends, Path, Query, Response, status
from neo4j import Driver

from app.api.deps import get_current_user, get_friend_service
from app.api.openapi import route_errors
from app.db.neo4j_db import get_driver
from app.models.schemas import (
    FriendCreatedResponse,
    FriendRemovedResponse,
    FriendsPage,
    MutualFriendsPage,
)
from app.services.friend_service import FriendService

USER_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
router = APIRouter(prefix="/api/v1", tags=["Friends"])


@router.get(
    "/friends",
    response_model=FriendsPage,
    summary="List your friends",
    operation_id="listFriends",
    responses=route_errors("USER_NOT_FOUND", protected=True),
)
def list_friends(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
    friend_service: FriendService = Depends(get_friend_service),
):
    items = friend_service.list_friends(
        driver, current_user["user_id"], offset=offset, limit=limit
    )
    return {"items": items, "limit": limit, "offset": offset}


@router.post(
    "/friends/{id}",
    response_model=FriendCreatedResponse,
    summary="Add yourself as a friend",
    operation_id="addFriend",
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"model": FriendCreatedResponse, "description": "Already connected."},
        **route_errors("CANNOT_FRIEND_SELF", "USER_NOT_FOUND", protected=True),
    },
)
def add_friend(
    response: Response,
    id: str = Path(..., pattern=USER_ID_PATTERN),
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
    friend_service: FriendService = Depends(get_friend_service),
):
    result = friend_service.add_friend(driver, current_user["user_id"], id)
    response.status_code = (
        status.HTTP_201_CREATED if result["created"] else status.HTTP_200_OK
    )
    return result


@router.delete(
    "/friends/{id}",
    response_model=FriendRemovedResponse,
    summary="Remove yourself as a friend",
    operation_id="removeFriend",
    responses=route_errors("CANNOT_FRIEND_SELF", "USER_NOT_FOUND", protected=True),
)
def remove_friend(
    id: str = Path(..., pattern=USER_ID_PATTERN),
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
    friend_service: FriendService = Depends(get_friend_service),
):
    return friend_service.remove_friend(driver, current_user["user_id"], id)


@router.get(
    "/users/{id}/mutual",
    response_model=MutualFriendsPage,
    summary="List mutual friends",
    operation_id="listMutualFriends",
    responses=route_errors("USER_NOT_FOUND", protected=True),
)
def mutual_friends(
    id: str = Path(..., pattern=USER_ID_PATTERN),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    driver: Driver = Depends(get_driver),
    current_user: dict = Depends(get_current_user),
    friend_service: FriendService = Depends(get_friend_service),
):
    items = friend_service.mutual_friends(
        driver,
        current_user["user_id"],
        id,
        offset=offset,
        limit=limit,
    )
    return {"items": items, "limit": limit, "offset": offset}
