"""Create the storage bucket and its CORS rules. Safe to run more than once.

python -m app.init_storage
"""

from app.config import get_settings
from app.storage import get_storage


def main() -> None:
    settings = get_settings()
    get_storage().ensure_bucket(settings.cors_origins)
    print(
        f"Bucket '{settings.s3_bucket}' ready at {settings.s3_endpoint_url} "
        f"(CORS allows {', '.join(settings.cors_origins)})"
    )


if __name__ == "__main__":
    main()
