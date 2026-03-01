"""Async wrappers around synchronous storage (boto3/MinIO) operations."""

import asyncio

from app.core.storage import (
    delete_file as _sync_delete,
    generate_avatar_key,
    generate_presigned_url as _sync_presigned,
    get_storage,
    upload_file as _sync_upload,
)


async def upload_file(data: bytes, key: str, content_type: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_upload, data, key, content_type)


async def get_user_storage_used(user_id: str) -> int:
    """Return total bytes stored for a user across editor/ and avatars/ prefixes."""
    from app.core.config import settings

    def _sync_get_used():
        client = get_storage()
        bucket = settings.MINIO_BUCKET_NAME
        total = 0
        for prefix in [f"editor/{user_id}/", f"avatars/{user_id}/"]:
            paginator = client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    total += obj["Size"]
        return total

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_get_used)


async def generate_presigned_url(key: str, expires_in: int) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_presigned, key, expires_in)


async def delete_file(key: str) -> None:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_delete, key)
