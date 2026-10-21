from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """App settings, read from environment variables (e.g. S3_BUCKET=woodshed).

    The defaults match the local services in docker-compose.yml, so the API and its
    tests run locally with no configuration. Production overrides every one of them.
    """

    database_url: str = "postgresql://woodshed:woodshed@localhost:5432/woodshed"

    s3_endpoint_url: str = "http://localhost:9000"
    # The address browsers use to reach storage, for presigned URLs. Inside Docker the
    # API reaches storage at http://storage:9000, which a browser can't resolve.
    s3_public_endpoint_url: str | None = None
    s3_access_key_id: str = "woodshed"
    s3_secret_access_key: str = "woodshed-secret"
    s3_bucket: str = "woodshed"
    s3_region: str = "us-east-1"

    # Websites allowed to upload to and download from storage directly.
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
