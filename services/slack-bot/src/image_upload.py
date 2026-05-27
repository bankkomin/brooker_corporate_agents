"""Upload Slack image attachments to MinIO for later embedding into decks/reports."""
from __future__ import annotations

import io
import os

import structlog
from minio import Minio
from minio.error import S3Error

logger = structlog.get_logger("slack-bot.image_upload")

# MUST align with services/shared/image_embed.py which reads from the same bucket.
DEFAULT_BUCKET = os.environ.get("MINIO_UPLOAD_BUCKET", "paperclip-uploads")
DEFAULT_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
DEFAULT_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
DEFAULT_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
DEFAULT_SECURE = os.environ.get("MINIO_SECURE", "false").lower() == "true"

# Slack's filetype field is lowercase. These are the image types we accept.
IMAGE_TYPES: frozenset[str] = frozenset({"png", "jpg", "jpeg", "gif"})

# JPEG content type override — Slack reports filetype="jpg" but the correct
# MIME type is image/jpeg. All other types follow the image/<filetype> pattern.
_CONTENT_TYPE_MAP: dict[str, str] = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
}


def get_minio_client() -> Minio:
    """Build a Minio client from env vars. Lazy + idempotent."""
    return Minio(
        DEFAULT_ENDPOINT,
        access_key=DEFAULT_ACCESS_KEY,
        secret_key=DEFAULT_SECRET_KEY,
        secure=DEFAULT_SECURE,
    )


def ensure_bucket(client: Minio, bucket: str = DEFAULT_BUCKET) -> None:
    """Create bucket if missing (idempotent)."""
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        logger.info("image_upload.bucket_created", bucket=bucket)


def build_minio_key(channel_id: str, file_id: str, filename: str) -> str:
    """Stable, predictable key shape downstream code can rely on.

    Pattern: slack-uploads/{channel_id}/{file_id}-{filename}
    Forward and back slashes in the filename component are replaced with
    underscores so the key remains a valid single-path-segment object name.
    """
    safe_name = filename.replace("/", "_").replace("\\", "_")
    return f"slack-uploads/{channel_id}/{file_id}-{safe_name}"


def upload_image_to_minio(
    *,
    file_bytes: bytes,
    filename: str,
    filetype: str,
    channel_id: str,
    file_id: str,
    client: Minio | None = None,
    bucket: str = DEFAULT_BUCKET,
) -> dict:
    """Upload image bytes to MinIO.

    Returns a dict with keys: minio_key, filename, file_id, bucket, size.
    Raises S3Error or RuntimeError on hard failure — never swallows silently.
    """
    if client is None:
        client = get_minio_client()

    ensure_bucket(client, bucket)

    key = build_minio_key(channel_id, file_id, filename)
    content_type = _CONTENT_TYPE_MAP.get(filetype.lower(), f"image/{filetype.lower()}")
    size = len(file_bytes)

    logger.info(
        "image_upload.uploading",
        key=key,
        bucket=bucket,
        size=size,
        content_type=content_type,
    )

    try:
        client.put_object(
            bucket_name=bucket,
            object_name=key,
            data=io.BytesIO(file_bytes),
            length=size,
            content_type=content_type,
        )
    except S3Error as exc:
        logger.error("image_upload.s3_error", key=key, bucket=bucket, error=str(exc))
        raise

    logger.info("image_upload.uploaded", key=key, bucket=bucket, size=size)

    return {
        "minio_key": key,
        "filename": filename,
        "file_id": file_id,
        "bucket": bucket,
        "size": size,
    }
