"""Async wrappers around synchronous storage (boto3/S3) operations."""

import asyncio

from app.core.storage import delete_file as _sync_delete
from app.core.storage import download_file as _sync_download
from app.core.storage import download_file_metadata as _sync_download_metadata
from app.core.storage import generate_presigned_url as _sync_presigned
from app.core.storage import get_file_size as _sync_get_file_size
from app.core.storage import get_storage
from app.core.storage import upload_file as _sync_upload


async def upload_file(data: bytes, key: str, content_type: str) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_upload, data, key, content_type)


async def get_user_storage_used(user_id: str) -> int:
    """Return total bytes stored for a user across editor/ and avatars/ prefixes."""
    from app.core.config import settings

    def _sync_get_used() -> int:
        client = get_storage()
        bucket = settings.S3_BUCKET_NAME
        total = 0
        for prefix in [f"editor/{user_id}/", f"avatars/{user_id}/"]:
            paginator = client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    total += obj["Size"]
        return total

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_get_used)


async def download_file(key: str) -> tuple[bytes, str]:
    """Download file from S3-compatible storage. Returns (data, content_type)."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_download, key)


async def download_file_metadata(key: str) -> tuple:
    """Get streaming body, content_type, and content_length from storage.

    Returns (streaming_body, content_type, content_length).
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_download_metadata, key)


async def generate_presigned_url(
    key: str, expires_in: int, filename: str | None = None
) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, _sync_presigned, key, expires_in, filename
    )


async def delete_file(key: str) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _sync_delete, key)


async def get_file_size(key: str) -> int:
    """Return the size in bytes of an object in storage. Returns 0 if not found."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_get_file_size, key)
