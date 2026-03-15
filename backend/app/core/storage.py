import uuid
from io import BytesIO
from typing import Any

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
from loguru import logger

from app.core.config import settings

_s3_client = None
_s3_presign_client = None  # Client using public URL endpoint for presigned URLs


def init_storage() -> None:
    """Initialize MinIO/S3 client and ensure bucket exists."""
    global _s3_client, _s3_presign_client
    endpoint_url = f"{'https' if settings.MINIO_USE_SSL else 'http'}://{settings.MINIO_ENDPOINT}"

    _s3_client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.MINIO_ROOT_USER,
        aws_secret_access_key=settings.MINIO_ROOT_PASSWORD,
        config=BotoConfig(signature_version="s3v4"),
        region_name="us-east-1",
    )

    # Presign client uses the public URL so the HMAC host matches what the browser sees
    if settings.MINIO_PUBLIC_URL:
        _s3_presign_client = boto3.client(
            "s3",
            endpoint_url=settings.MINIO_PUBLIC_URL.rstrip("/"),
            aws_access_key_id=settings.MINIO_ROOT_USER,
            aws_secret_access_key=settings.MINIO_ROOT_PASSWORD,
            config=BotoConfig(signature_version="s3v4"),
            region_name="us-east-1",
        )

    # Ensure bucket exists
    bucket = settings.MINIO_BUCKET_NAME
    try:
        _s3_client.head_bucket(Bucket=bucket)
        logger.info("Storage bucket exists", extra={"bucket": bucket})
    except _s3_client.exceptions.ClientError:
        _s3_client.create_bucket(Bucket=bucket)
        logger.info("Storage bucket created", extra={"bucket": bucket})


def get_storage() -> Any:
    if _s3_client is None:
        raise RuntimeError("Storage client not initialized. Call init_storage() first.")
    return _s3_client


def close_storage() -> None:
    """Close the boto3 S3 client and release its resources."""
    global _s3_client, _s3_presign_client
    if _s3_client is not None:
        _s3_client.close()
        _s3_client = None
    if _s3_presign_client is not None:
        _s3_presign_client.close()
        _s3_presign_client = None


def upload_file(data: bytes, key: str, content_type: str) -> str:
    """Upload file to MinIO. Returns the storage key."""
    client = get_storage()
    client.put_object(
        Bucket=settings.MINIO_BUCKET_NAME,
        Key=key,
        Body=BytesIO(data),
        ContentLength=len(data),
        ContentType=content_type,
    )
    logger.info("File uploaded", extra={"key": key, "size": len(data)})
    return key


def generate_presigned_url(key: str, expires_in: int = 3600, filename: str | None = None) -> str:
    """Generate presigned download URL.

    When MINIO_PUBLIC_URL is set, uses a client configured with that endpoint so
    the HMAC signature is computed against the public host (e.g. localhost:19000).
    Rewriting the host after signing would break the signature.

    When ``filename`` is provided, sets Content-Disposition so the browser uses
    that name for the downloaded file.
    """
    client = _s3_presign_client if _s3_presign_client is not None else get_storage()
    params: dict = {"Bucket": settings.MINIO_BUCKET_NAME, "Key": key}
    if filename:
        # ASCII-safe fallback for the filename parameter (non-ASCII chars → _)
        import os
        import re

        base, ext = os.path.splitext(filename)
        ascii_base = re.sub(r"[^\x20-\x7E]", "_", base).strip(" _") or "export"
        ascii_fallback = ascii_base + ext
        # NOTE: Do NOT pre-encode the filename for filename* — boto3 will
        # URL-encode the entire ResponseContentDisposition query parameter.
        # Pre-encoding causes double-encoding (e.g. %E4 → %25E4 = garbled).
        params["ResponseContentDisposition"] = f'attachment; filename="{ascii_fallback}"'
    return str(
        client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expires_in,
        )
    )


def download_file(key: str) -> tuple[bytes, str]:
    """Download file from MinIO. Returns (data, content_type)."""
    client = get_storage()
    resp = client.get_object(Bucket=settings.MINIO_BUCKET_NAME, Key=key)
    data = resp["Body"].read()
    content_type = resp.get("ContentType", "application/octet-stream")
    return data, content_type


def delete_file(key: str) -> None:
    """Delete file from MinIO."""
    client = get_storage()
    client.delete_object(Bucket=settings.MINIO_BUCKET_NAME, Key=key)
    logger.info("File deleted", extra={"key": key})


def get_file_size(key: str) -> int:
    """Return the size in bytes of an object in MinIO. Returns 0 if not found."""
    client = get_storage()
    try:
        resp = client.head_object(Bucket=settings.MINIO_BUCKET_NAME, Key=key)
        return int(resp.get("ContentLength", 0))
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return 0
        raise


def generate_avatar_key(user_id: str, extension: str) -> str:
    """Generate unique storage key for avatar."""
    return f"avatars/{user_id}/{uuid.uuid4().hex}{extension}"


def generate_form_banner_key(form_id: str, extension: str) -> str:
    """Generate unique storage key for form banner."""
    return f"forms/banners/{form_id}/{uuid.uuid4().hex}{extension}"


def generate_form_upload_key(form_id: str, extension: str) -> str:
    """Generate unique storage key for form file upload."""
    return f"forms/uploads/{form_id}/{uuid.uuid4().hex}{extension}"


def generate_form_export_key(form_id: str, task_id: str) -> str:
    """Generate storage key for form CSV export."""
    return f"exports/forms/{form_id}/{task_id}.csv"


# ── Album storage keys ─────────────────────────────────────────────────────


def album_photo_key(album_id: str, filename_uuid: str, ext: str) -> str:
    """Generate storage key for an album photo."""
    return f"albums/{album_id}/photos/{filename_uuid}.{ext}"


def album_thumbnail_key(album_id: str, filename_uuid: str) -> str:
    """Generate storage key for an album photo thumbnail."""
    return f"albums/{album_id}/thumbs/{filename_uuid}.webp"


def album_zip_key(album_id: str, filename_uuid: str, ext: str) -> str:
    """Generate storage key for an album ZIP file."""
    return f"albums/{album_id}/files/{filename_uuid}.{ext}"
