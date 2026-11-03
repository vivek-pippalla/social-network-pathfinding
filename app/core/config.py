from functools import lru_cache

from pydantic import ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode
from typing import Annotated


PLACEHOLDER_SECRETS = {
    "change-me",
    "changeme",
    "your-secret-key-here-use-openssl-rand-hex-32",
    "your-secret-key-here",
    "replace-with-at-least-32-random-characters",
    "secret",
    "password",
}
PLACEHOLDER_PASSWORDS = {
    "your-neo4j-password-here",
    "password123",
    "password",
    "replace-with-a-private-password",
}
EXPLICIT_TEST_SECRET = "test-only-secret-key-32-bytes-minimum"


class Settings(BaseSettings):
    APP_ENV: str = "dev"
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    MAX_PATH_DEPTH: int = 6
    NEO4J_QUERY_TIMEOUT_SECONDS: float = 5.0
    REDIS_SOCKET_TIMEOUT_SECONDS: float = 0.2
    CACHE_TTL_SECONDS: int = 300
    NEGATIVE_CACHE_TTL_SECONDS: int = 60
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ENABLE_DOCS: bool = True
    AUTO_SCHEMA: bool = True
    ALLOWED_ORIGINS: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # Kept temporarily because the existing AWS/ingestion code still imports these.
    AWS_REGION: str = "ap-south-1"
    AWS_S3_BUCKET: str = ""
    AWS_S3_DATASET_KEY: str = "datasets/facebook_combined.txt.gz"
    CLOUDWATCH_ENABLED: bool = False
    CLOUDWATCH_LOG_GROUP: str = "/social-network-pathfinding/app"
    CLOUDWATCH_LOG_RETENTION_DAYS: int = 14

    model_config = ConfigDict(env_file=".env", extra="ignore")

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("SECRET_KEY must contain at least 32 characters")
        if value.strip().lower() in PLACEHOLDER_SECRETS:
            raise ValueError("SECRET_KEY must not be a placeholder value")
        return value

    @field_validator("NEO4J_PASSWORD")
    @classmethod
    def validate_neo4j_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("NEO4J_PASSWORD must contain at least 8 characters")
        if value.strip().lower() in PLACEHOLDER_PASSWORDS:
            raise ValueError("NEO4J_PASSWORD must not be a placeholder value")
        return value

    @field_validator("APP_ENV")
    @classmethod
    def validate_app_env(cls, value: str) -> str:
        if value not in {"dev", "test", "prod"}:
            raise ValueError("APP_ENV must be dev, test, or prod")
        return value

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def reject_test_secret_outside_test(self):
        if self.APP_ENV != "test" and self.SECRET_KEY == EXPLICIT_TEST_SECRET:
            raise ValueError(
                "the explicit test secret is allowed only when APP_ENV=test"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


# Temporary compatibility accessor; removed when legacy imports are migrated.
settings = get_settings()
