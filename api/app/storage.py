"""S3-compatible object storage: RustFS locally, Cloudflare R2 in production.

Audio never passes through the API. Browsers upload and download directly with
presigned URLs: short-lived links, signed with our secret key, that allow exactly
one action on one file.

Layout: everything for a song lives under one prefix, so it can be deleted at once.
    songs/{song_id}/original.mp3
    songs/{song_id}/stems/vocals.mp3
"""

from functools import lru_cache
from uuid import UUID

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import Settings, get_settings

UPLOAD_URL_EXPIRY_SECONDS = 15 * 60
DOWNLOAD_URL_EXPIRY_SECONDS = 60 * 60
NOT_FOUND_CODES = {"404", "NoSuchKey", "NoSuchBucket", "NotFound"}


def song_prefix(song_id: UUID) -> str:
    return f"songs/{song_id}/"


def original_key(song_id: UUID, extension: str) -> str:
    return f"{song_prefix(song_id)}original.{extension.lower().lstrip('.')}"


def stem_key(song_id: UUID, stem: str, extension: str = "mp3") -> str:
    return f"{song_prefix(song_id)}stems/{stem}.{extension}"


def _client(settings: Settings, endpoint_url: str) -> BaseClient:
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


class Storage:
    def __init__(self, settings: Settings) -> None:
        self.bucket = settings.s3_bucket
        self._s3 = _client(settings, settings.s3_endpoint_url)
        # A presigned URL is signed for one host, so it has to be created with the
        # address the browser will use. Signing happens locally; no request is sent.
        self._signer = _client(
            settings, settings.s3_public_endpoint_url or settings.s3_endpoint_url
        )

    def presigned_upload_url(self, key: str, content_type: str) -> str:
        """A URL the browser can PUT one file to. The Content-Type is part of the
        signature, so the upload must send exactly this content type."""
        return self._signer.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=UPLOAD_URL_EXPIRY_SECONDS,
        )

    def presigned_download_url(self, key: str, download_name: str | None = None) -> str:
        """A URL the browser can GET one file from. With `download_name`, the browser
        saves the file under that name instead of playing it."""
        params = {"Bucket": self.bucket, "Key": key}
        if download_name:
            params["ResponseContentDisposition"] = f'attachment; filename="{download_name}"'
        return self._signer.generate_presigned_url(
            "get_object", Params=params, ExpiresIn=DOWNLOAD_URL_EXPIRY_SECONDS
        )

    def object_size(self, key: str) -> int | None:
        """Size in bytes, or None if the file doesn't exist (e.g. the upload never ran)."""
        try:
            return self._s3.head_object(Bucket=self.bucket, Key=key)["ContentLength"]
        except ClientError as err:
            if err.response["Error"]["Code"] in NOT_FOUND_CODES:
                return None
            raise

    def delete_prefix(self, prefix: str) -> int:
        """Delete every file under a prefix, e.g. everything for one song."""
        # An empty prefix would match the whole bucket.
        if not prefix.endswith("/") or prefix == "/":
            raise ValueError(f"refusing to delete prefix {prefix!r}; it must end in '/'")
        deleted = 0
        # Listing and deleting both work in batches of up to 1,000 files.
        for page in self._s3.get_paginator("list_objects_v2").paginate(
            Bucket=self.bucket, Prefix=prefix
        ):
            objects = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
            if objects:
                self._s3.delete_objects(Bucket=self.bucket, Delete={"Objects": objects})
                deleted += len(objects)
        return deleted

    def ensure_bucket(self, cors_origins: list[str]) -> None:
        """Create the bucket if needed and allow our frontend to use it directly."""
        try:
            self._s3.head_bucket(Bucket=self.bucket)
        except ClientError as err:
            if err.response["Error"]["Code"] not in NOT_FOUND_CODES:
                raise
            self._s3.create_bucket(Bucket=self.bucket)
        self._s3.put_bucket_cors(
            Bucket=self.bucket,
            CORSConfiguration={
                "CORSRules": [
                    {
                        "AllowedOrigins": cors_origins,
                        "AllowedMethods": ["GET", "HEAD", "PUT"],
                        "AllowedHeaders": ["*"],
                        "ExposeHeaders": ["ETag"],
                        "MaxAgeSeconds": 3600,
                    }
                ]
            },
        )


@lru_cache
def get_storage() -> Storage:
    return Storage(get_settings())
