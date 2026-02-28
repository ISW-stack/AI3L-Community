import uuid
from io import BytesIO

import boto3
from botocore.config import Config as BotoConfig
from loguru import logger

from app.core.config import settings

_s3_client = None


def init_storage() -> None:
    """Initialize MinIO/S3 client and ensure bucket exists."""
    global _s3_client
    endpoint_url = f"{'https' if settings.MINIO_USE_SSL else 'http'}://{settings.MINIO_ENDPOINT}"

    _s3_client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
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


def get_storage():
    if _s3_client is None:
        raise RuntimeError("Storage client not initialized. Call init_storage() first.")
    return _s3_client


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


def generate_presigned_url(key: str, expires_in: int = 3600) -> str:
    """Generate presigned download URL."""
    client = get_storage()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.MINIO_BUCKET_NAME, "Key": key},
        ExpiresIn=expires_in,
    )


def delete_file(key: str) -> None:
    """Delete file from MinIO."""
    client = get_storage()
    client.delete_object(Bucket=settings.MINIO_BUCKET_NAME, Key=key)
    logger.info("File deleted", extra={"key": key})


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
