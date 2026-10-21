import os
import socket
import uuid
from collections.abc import Iterator
from urllib.parse import urlparse

import pytest

from app.config import Settings
from app.storage import Storage


@pytest.fixture(scope="session")
def storage() -> Iterator[Storage]:
    """Storage connected to a temporary bucket on the local S3 server.

    Skipped locally if the server isn't running, but required in CI (where GitHub
    sets CI=true) so a broken setup can't silently skip these tests.
    """
    settings = Settings(s3_bucket=f"test-{uuid.uuid4().hex[:12]}")
    # Check quickly whether anything is listening; boto3's own retries take ~25s to give up.
    endpoint = urlparse(settings.s3_endpoint_url)
    try:
        socket.create_connection((endpoint.hostname, endpoint.port or 80), timeout=1).close()
    except OSError:
        if os.environ.get("CI"):
            raise
        pytest.skip("storage isn't running; start it with: docker compose up -d storage")

    storage = Storage(settings)
    storage.ensure_bucket(settings.cors_origins)

    yield storage

    # Empty and remove the temporary bucket.
    s3 = storage._s3
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=storage.bucket):
        for obj in page.get("Contents", []):
            s3.delete_object(Bucket=storage.bucket, Key=obj["Key"])
    s3.delete_bucket(Bucket=storage.bucket)
