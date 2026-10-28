from pydantic_settings import BaseSettings
from pydantic import ConfigDict


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
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # AWS S3 (Dataset Ingestion)
    AWS_REGION: str = "ap-south-1"
    AWS_S3_BUCKET: str = ""
    AWS_S3_DATASET_KEY: str = "datasets/facebook_combined.txt.gz"

    # Amazon CloudWatch (Structured Logging)
    CLOUDWATCH_ENABLED: bool = False
    CLOUDWATCH_LOG_GROUP: str = "/social-network-pathfinding/app"
    CLOUDWATCH_LOG_RETENTION_DAYS: int = 14

    model_config = ConfigDict(env_file=".env", extra="ignore")


settings = Settings()
