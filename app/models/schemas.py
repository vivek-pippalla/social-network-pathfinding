from typing import Generic, Literal, Optional, TypeVar

import email_validator
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

email_validator.TEST_ENVIRONMENT = True


# ─── User ────────────────────────────────────────────────────────────────────


class PublicUserResponse(BaseModel):
    id: str
    name: str
    source: str = "snap"

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"id": "42", "name": "User_42", "source": "snap"}]
        }
    )


class OwnProfileResponse(PublicUserResponse):
    email: EmailStr

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "3d4c8a3f5e6b7c8d9a0b1c2d3e4f5a6b",
                    "name": "Ada",
                    "source": "app",
                    "email": "ada@example.test",
                }
            ]
        }
    )


# ─── Connection ──────────────────────────────────────────────────────────────


class ConnectionResponse(BaseModel):
    message: str


class FriendCreatedResponse(BaseModel):
    created: bool

    model_config = ConfigDict(json_schema_extra={"examples": [{"created": True}]})


class FriendRemovedResponse(BaseModel):
    removed: bool

    model_config = ConfigDict(json_schema_extra={"examples": [{"removed": True}]})


ItemT = TypeVar("ItemT")


class PaginationPage(BaseModel, Generic[ItemT]):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "items": [{"id": "42", "name": "User_42", "source": "snap"}],
                    "limit": 20,
                    "offset": 0,
                    "total": None,
                }
            ]
        }
    )

    items: list[ItemT]
    limit: int
    offset: int
    total: int | None = None


FriendsPage = PaginationPage[PublicUserResponse]
MutualFriendsPage = PaginationPage[PublicUserResponse]


# ─── Pathfinding ─────────────────────────────────────────────────────────────


class PathNode(BaseModel):
    id: str
    name: str


class PathResponse(BaseModel):
    start_user: str
    end_user: str
    path: list[PathNode]
    hops: int
    cached: bool

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "start_user": "1",
                    "end_user": "9",
                    "path": [
                        {"id": "1", "name": "User_1"},
                        {"id": "4", "name": "User_4"},
                        {"id": "9", "name": "User_9"},
                    ],
                    "hops": 2,
                    "cached": False,
                }
            ]
        }
    )


# ─── Suggestions ─────────────────────────────────────────────────────────────


class SuggestedUser(BaseModel):
    user_id: str
    name: str
    mutual_friends: int


class SuggestionResponse(PaginationPage[SuggestedUser]):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "items": [
                        {
                            "user_id": "candidate-1",
                            "name": "Morgan",
                            "mutual_friends": 3,
                        }
                    ],
                    "limit": 20,
                    "offset": 0,
                    "total": None,
                }
            ]
        }
    )


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"

    model_config = ConfigDict(json_schema_extra={"examples": [{"status": "ok"}]})


class ReadinessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    components: dict[str, Literal["ok", "degraded"]]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "ok",
                    "components": {"neo4j": "ok", "redis": "degraded"},
                }
            ]
        }
    )


class ErrorObject(BaseModel):
    code: str
    message: str
    request_id: str
    details: list[dict] = Field(default_factory=list)


class ErrorEnvelope(BaseModel):
    error: ErrorObject


# ─── Authentication ──────────────────────────────────────────────────────────


class UserRegister(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Ada",
                    "email": "ada@example.test",
                    "password": "a-long-demo-password",
                }
            ]
        }
    )

    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def password_must_differ_from_identity(self):
        if self.password.casefold() in {
            str(self.email).casefold(),
            self.name.casefold(),
        }:
            raise ValueError("password must differ from email and name")
        return self


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"examples": [{"name": "Ada Lovelace"}]}
    )

    name: str = Field(min_length=1, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "access_token": "eyJhbGciOiJIUzI1NiJ9.example.signature",
                    "token_type": "bearer",
                    "expires_in": 1800,
                }
            ]
        }
    )


UserResponse = PublicUserResponse
