"""Celery task: VirusTotal hash-only file check."""

import hashlib
from typing import Any

import requests  # type: ignore[import-untyped]
from loguru import logger

from app.celery_app import celery
from app.core.config import settings


@celery.task(bind=True, max_retries=2, default_retry_delay=60)
def check_virustotal(self: Any, file_hash: str, storage_key: str) -> dict:
    """Query VirusTotal for a file SHA-256 hash; delete if malicious."""
    api_key = settings.VT_API_KEY
    if not api_key:
        logger.debug("VT_API_KEY not set, skipping VirusTotal check")
        return {"status": "skipped", "reason": "no_api_key"}

    url = f"https://www.virustotal.com/api/v3/files/{file_hash}"
    headers = {"x-apikey": api_key}

    try:
        resp = requests.get(url, headers=headers, timeout=30)
    except requests.RequestException as exc:
        logger.warning("VirusTotal request failed", extra={"error": str(exc)})
        raise self.retry(exc=exc)

    if resp.status_code == 404:
        logger.info("File hash not found in VirusTotal", extra={"hash": file_hash})
        return {"status": "not_found"}

    if resp.status_code != 200:
        logger.warning("VirusTotal unexpected status", extra={"status": resp.status_code})
        return {"status": "error", "code": resp.status_code}

    data = resp.json()
    stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
    malicious = stats.get("malicious", 0)
    suspicious = stats.get("suspicious", 0)

    if malicious > 0 or suspicious > 0:
        logger.warning(
            "VirusTotal flagged file as malicious",
            extra={
                "hash": file_hash,
                "key": storage_key,
                "malicious": malicious,
                "suspicious": suspicious,
            },
        )
        # Delete the file from storage
        try:
            from app.core.storage import delete_file

            delete_file(storage_key)
            logger.info("Deleted malicious file from storage", extra={"key": storage_key})
        except Exception as e:
            logger.error(
                "Failed to delete malicious file", extra={"key": storage_key, "error": str(e)}
            )

        return {"status": "malicious", "malicious": malicious, "suspicious": suspicious}

    logger.info("VirusTotal check passed", extra={"hash": file_hash})
    return {"status": "clean"}


def compute_sha256(data: bytes) -> str:
    """Compute SHA-256 hash of file data."""
    return hashlib.sha256(data).hexdigest()
