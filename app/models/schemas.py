from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


# ─── User ────────────────────────────────────────────────────────────────────

class PublicUserResponse(BaseModel):
    id: str
    name: str
    source: str = "snap"


class OwnProfileResponse(PublicUserResponse):
    email: EmailStr


# ─── Connection ──────────────────────────────────────────────────────────────

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
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def password_must_differ_from_identity(self):
        if self.password.casefold() in {
            str(self.email).casefold(),
            self.name.casefold(),
        }:
            raise ValueError("password must differ from email and name")
        return self


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


UserResponse = PublicUserResponse
