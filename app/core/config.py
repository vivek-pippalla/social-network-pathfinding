from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password123"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Cache
    CACHE_TTL_SECONDS: int = 3600

    # JWT Authentication
    # Generate a real secret with: python -c "import secrets; print(secrets.token_hex(32))"
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    class Config:
        env_file = ".env"


settings = Settings()
