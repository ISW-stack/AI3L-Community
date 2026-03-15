"""Thumbnail generation Celery task for album photos."""

import asyncio
import io
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

logger = logging.getLogger(__name__)


def _run_async(coro: Any) -> Any:
    """Run an async coroutine from a sync Celery task context."""
    with ThreadPoolExecutor(1) as pool:
        return pool.submit(asyncio.run, coro).result()


async def _update_thumbnail_key(photo_id: str, thumbnail_key: str) -> None:
    """Update the thumbnail_key in the DB for the given photo."""
    import uuid

    from app.core.config import settings
    from app.core.database import get_pool, init_db_pool
    from app.repositories import album_repo

    try:
        pool = get_pool()
    except RuntimeError:
        pool = await init_db_pool(settings.DATABASE_URL)

    async with pool.acquire() as conn:
        await album_repo.set_thumbnail_key(conn, uuid.UUID(photo_id), thumbnail_key)


# Lazy import of celery to avoid circular imports at module level
def _get_celery():  # type: ignore[no-untyped-def]
    from app.celery_app import celery

    return celery


# Register the task — must be at module level for Celery autodiscovery
from app.celery_app import celery  # noqa: E402


@celery.task(name="generate_thumbnail", bind=True, max_retries=2)
def generate_thumbnail_task(
    self: Any, storage_key: str, thumbnail_key: str, photo_id: str
) -> dict[str, str]:
    """Download image from MinIO, resize to 400x400, save as WebP, update DB."""
    # Import MinIO client directly (sync context, not boto3)
    from minio import Minio
    from PIL import Image, ImageOps

    from app.core.config import settings
    from app.core.constants import ALBUM_THUMBNAIL_QUALITY, ALBUM_THUMBNAIL_SIZE

    client = Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ROOT_USER,
        secret_key=settings.MINIO_ROOT_PASSWORD,
        secure=settings.MINIO_USE_SSL,
    )
    bucket = settings.MINIO_BUCKET_NAME

    try:
        # 1. Download original
        response = client.get_object(bucket, storage_key)
        data = response.read()
        response.close()
        response.release_conn()

        # 2. Safety check — limit decompression bomb risk
        Image.MAX_IMAGE_PIXELS = 50_000_000  # 50MP limit

        # 3. Resize
        img: Any = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)  # fix orientation
        img.thumbnail(ALBUM_THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

        # 4. Convert to RGB if necessary (e.g. RGBA PNGs)
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")

        # 5. Save as WebP
        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=ALBUM_THUMBNAIL_QUALITY)
        buf.seek(0)
        thumb_size = buf.getbuffer().nbytes

        # 6. Upload thumbnail
        client.put_object(
            bucket,
            thumbnail_key,
            buf,
            thumb_size,
            content_type="image/webp",
        )

        # 7. Update DB with thumbnail key
        _run_async(_update_thumbnail_key(photo_id, thumbnail_key))

        logger.info("Thumbnail generated: %s -> %s", storage_key, thumbnail_key)
        return {"status": "success", "thumbnail_key": thumbnail_key}

    except Exception:
        logger.exception("Thumbnail generation failed for %s", storage_key)
        raise
