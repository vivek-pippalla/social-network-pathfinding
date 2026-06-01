from typing import Optional
from pydantic import BaseModel


# ─── User ────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    name: str
    email: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    name: str
    email: Optional[str] = None


# ─── Connection ──────────────────────────────────────────────────────────────

class ConnectionCreate(BaseModel):
    user_id_1: str
    user_id_2: str


class ConnectionResponse(BaseModel):
    message: str


# ─── Pathfinding ─────────────────────────────────────────────────────────────

class PathResponse(BaseModel):
    start_user: str
    end_user: str
    path: list[str]
    hops: int
    cached: bool


# ─── Suggestions ─────────────────────────────────────────────────────────────

class SuggestedUser(BaseModel):
    user_id: str
    mutual_friends: int


class SuggestionResponse(BaseModel):
    user_id: str
    suggestions: list[SuggestedUser]


# ─── Authentication ──────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    name: str
    email: str
    password: str


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: Optional[str] = None
