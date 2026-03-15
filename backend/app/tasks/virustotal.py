"""Celery task: VirusTotal hash-only file check."""

import asyncio
import hashlib
from concurrent.futures import ThreadPoolExecutor
from typing import IO, Any, Union

import requests  # type: ignore[import-untyped]
from loguru import logger

from app.celery_app import celery
from app.core.config import settings
from app.core.database import get_pool, init_db_pool


def _run_async(coro: Any) -> Any:
    """Run an async coroutine from sync Celery task, cross-platform safe."""
    with ThreadPoolExecutor(1) as pool:
        return pool.submit(asyncio.run, coro).result()


async def _ensure_pool() -> None:
    """Ensure DB pool is available (worker may not have it)."""
    try:
        get_pool()
    except RuntimeError:
        await init_db_pool(settings.DATABASE_URL)


async def _insert_pending(storage_key: str) -> None:
    """Insert a pending scan record."""
    await _ensure_pool()
    from app.repositories import file_scan_repo

    await file_scan_repo.insert(storage_key)


async def _update_scan(
    storage_key: str,
    status: str,
    scan_id: str | None = None,
    positives: int | None = None,
    total: int | None = None,
) -> None:
    """Update scan record with results."""
    await _ensure_pool()
    from app.repositories import file_scan_repo

    await file_scan_repo.update_status(storage_key, status, scan_id, positives, total)


async def _decrement_owner_storage(storage_key: str, file_size: int) -> None:
    """Parse user_id from storage key and decrement their storage counter."""
    import uuid

    await _ensure_pool()
    from app.repositories import user_repo

    # Key pattern: editor/{user_id}/{filename}
    parts = storage_key.split("/")
    if len(parts) >= 2:
        try:
            owner_uuid = uuid.UUID(parts[1])
            await user_repo.increment_storage_used(owner_uuid, -file_size)
            logger.info(
                "Decremented storage for user after malicious file deletion",
                extra={"user_id": parts[1], "key": storage_key, "size": file_size},
            )
        except (ValueError, Exception) as e:
            logger.warning(
                "Failed to decrement storage after malicious file deletion",
                extra={"key": storage_key, "error": str(e)},
            )


@celery.task(bind=True, max_retries=2, default_retry_delay=60)
def check_virustotal(self: Any, file_hash: str, storage_key: str) -> dict:
    """Query VirusTotal for a file SHA-256 hash; delete if malicious."""

    # Insert pending scan record
    try:
        _run_async(_insert_pending(storage_key))
    except Exception:
        logger.error("Failed to insert pending scan record for key=%s", storage_key, exc_info=True)

    api_key = settings.VT_API_KEY
    if not api_key:
        logger.warning("VT_API_KEY not set — file scan skipped (not verified)")
        try:
            _run_async(_update_scan(storage_key, "skipped"))
        except Exception:
            logger.error("Failed to update scan record to skipped", exc_info=True)
        return {"status": "skipped", "reason": "no_api_key"}

    url = f"https://www.virustotal.com/api/v3/files/{file_hash}"
    headers = {"x-apikey": api_key}

    try:
        resp = requests.get(url, headers=headers, timeout=30)
    except requests.RequestException as exc:
        logger.warning("VirusTotal request failed", extra={"error": str(exc)})
        raise self.retry(exc=exc)

    if resp.status_code == 404:
        logger.warning(
            "File hash not found in VirusTotal — marking as unknown (fail-close)",
            extra={"hash": file_hash},
        )
        try:
            _run_async(_update_scan(storage_key, "unknown"))
        except Exception:
            logger.error("Failed to update scan record to unknown", exc_info=True)
        return {"status": "not_found"}

    if resp.status_code != 200:
        logger.warning(
            "VirusTotal unexpected status — retrying or marking as error (fail-close)",
            extra={"status": resp.status_code},
        )
        try:
            raise self.retry(exc=RuntimeError(f"VT returned {resp.status_code}"))
        except self.MaxRetriesExceededError:
            logger.error(
                "VirusTotal retries exhausted — marking as error",
                extra={"status": resp.status_code, "key": storage_key},
            )
            try:
                _run_async(_update_scan(storage_key, "error"))
            except Exception:
                logger.error("Failed to update scan record to error", exc_info=True)
            return {"status": "error", "code": resp.status_code}

    try:
        data = resp.json()
    except (ValueError, requests.exceptions.JSONDecodeError):
        logger.warning(
            "VirusTotal response is not valid JSON — marking as error (fail-close)",
            extra={"status": resp.status_code},
        )
        try:
            _run_async(_update_scan(storage_key, "error"))
        except Exception:
            logger.error("Failed to update scan record to error", exc_info=True)
        return {"status": "error", "reason": "invalid_json"}
    stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
    malicious = stats.get("malicious", 0)
    suspicious = stats.get("suspicious", 0)
    total_engines = sum(stats.values()) if stats else 0
    positives_count = malicious + suspicious
    scan_id = data.get("data", {}).get("id")

    if positives_count > 0:
        logger.warning(
            "VirusTotal flagged file as malicious",
            extra={
                "hash": file_hash,
                "key": storage_key,
                "malicious": malicious,
                "suspicious": suspicious,
            },
        )

        # Update record to malicious
        try:
            _run_async(
                _update_scan(storage_key, "malicious", scan_id, positives_count, total_engines)
            )
        except Exception:
            logger.error("Failed to update scan record to malicious", exc_info=True)

        # Delete the file from storage and decrement owner's storage quota
        try:
            from app.core.async_storage import delete_file, get_file_size

            file_size = _run_async(get_file_size(storage_key))
            _run_async(delete_file(storage_key))
            logger.info("Deleted malicious file from storage", extra={"key": storage_key})
            if file_size > 0:
                try:
                    _run_async(_decrement_owner_storage(storage_key, file_size))
                except Exception:
                    logger.error(
                        "Failed to decrement storage after malicious deletion",
                        extra={"key": storage_key},
                        exc_info=True,
                    )
        except Exception as e:
            logger.error(
                "Failed to delete malicious file", extra={"key": storage_key, "error": str(e)}
            )

        return {"status": "malicious", "malicious": malicious, "suspicious": suspicious}

    # File is clean
    try:
        _run_async(_update_scan(storage_key, "clean", scan_id, 0, total_engines))
    except Exception:
        logger.error("Failed to update scan record to clean", exc_info=True)

    logger.info("VirusTotal check passed", extra={"hash": file_hash})
    return {"status": "clean"}


def compute_sha256(source: Union[bytes, IO[bytes]]) -> str:
    """Compute SHA-256 hash of file data.

    Accepts raw bytes or a file-like object.  When a file-like object is
    provided the content is read in 8 KiB chunks to avoid holding the
    entire payload in a single hashlib buffer, and the file position is
    reset to the beginning afterwards so the caller can still read it.
    """
    _CHUNK_SIZE = 8192
    h = hashlib.sha256()

    if isinstance(source, bytes):
        # Stream via memoryview to avoid copying the full buffer
        mv = memoryview(source)
        for offset in range(0, len(mv), _CHUNK_SIZE):
            h.update(mv[offset : offset + _CHUNK_SIZE])
    else:
        while True:
            chunk = source.read(_CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
        source.seek(0)

    return h.hexdigest()
