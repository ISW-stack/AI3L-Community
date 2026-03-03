import re
import uuid

from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from loguru import logger

from app.core.async_storage import download_file as async_download_file
from app.core.async_storage import generate_presigned_url as async_presigned_url
from app.core.async_storage import get_user_storage_used
from app.core.async_storage import upload_file as async_upload_file
from app.core.config import settings
from app.core.constants import MAX_EDITOR_FILE_SIZE, RATE_LIMIT_FILE_UPLOAD
from app.core.deps import require_role
from app.core.file_validation import validate_editor_file
from app.core.rate_limit import check_rate_limit
from app.core.redis import get_redis
from app.repositories import file_scan_repo
from app.schemas.file import FileUploadResponse

router = APIRouter(prefix="/files", tags=["files"])

_SAFE_KEY_RE = re.compile(r"^[a-zA-Z0-9/_.\-]+$")


@router.post(
    "/upload/editor", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED
)
async def upload_editor_file(
    file: UploadFile,
    request: Request,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> FileUploadResponse:
    """Upload file for rich text editor (PNG, JPEG, PDF, DOCX). Max 20MB."""
    user_id = current_user["sub"]
    if not await check_rate_limit(f"rl:upload:{user_id}", *RATE_LIMIT_FILE_UPLOAD):
        raise HTTPException(status_code=429, detail="Too many uploads. Try again later.")
    filename = file.filename or "unnamed"
    data = await file.read(MAX_EDITOR_FILE_SIZE + 1)
    if len(data) > MAX_EDITOR_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 20MB limit.",
        )
    expected_type, data = validate_editor_file(filename, data)

    # Acquire per-user upload lock to prevent concurrent quota bypass
    redis = get_redis()
    lock_key = f"upload_lock:{user_id}"
    acquired = await redis.set(lock_key, "1", nx=True, ex=120)
    if not acquired:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Another upload is in progress. Please wait.",
        )

    try:
        # Storage quota check (safe under lock)
        used = await get_user_storage_used(current_user["sub"])
        if used + len(data) > settings.MAX_USER_STORAGE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Storage quota exceeded (1 GB limit).",
            )

        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        key = f"editor/{current_user['sub']}/{uuid.uuid4().hex}{ext}"
        await async_upload_file(data, key, expected_type)
    finally:
        await redis.delete(lock_key)

    # Return stable proxy URL instead of expiring presigned URL
    url = f"/api/v1/files/content/{key}"

    # Insert pending scan record
    try:
        await file_scan_repo.insert(key)
    except Exception:
        logger.warning("Failed to insert pending scan record for key=%s", key, exc_info=True)

    # Fire-and-forget VirusTotal check (lazy import to avoid celery dependency at module load)
    scan_task_id = None
    try:
        from app.tasks.virustotal import check_virustotal, compute_sha256

        file_hash = compute_sha256(data)
        result = check_virustotal.delay(file_hash, key)
        scan_task_id = result.id
    except ImportError:
        pass  # VirusTotal not configured
    except Exception:
        logger.warning("VirusTotal scan trigger failed for key=%s", key, exc_info=True)

    return FileUploadResponse(
        key=key,
        url=url,
        filename=filename,
        content_type=expected_type,
        size=len(data),
        scan_task_id=scan_task_id,
    )


@router.get("/content/{key:path}")
async def serve_file(
    key: str,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> Response:
    """Serve file content from storage via proxy.

    Editor files (editor/*) are accessible to any authenticated user.
    Other files require ownership or admin role.
    """
    if ".." in key or not _SAFE_KEY_RE.match(key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file key.",
        )

    is_editor_file = key.startswith("editor/")
    is_admin = current_user["role"] in ("SUPER_ADMIN", "ADMIN")

    # Editor files are readable by any authenticated member (they're embedded in public posts)
    if not is_editor_file and not is_admin:
        owns_file = key.startswith(f"avatars/{current_user['sub']}")
        if not owns_file:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this file.",
            )

    # Block files flagged as malicious by VirusTotal
    try:
        scan = await file_scan_repo.find_by_key(key)
        if scan and scan["status"] == "malicious":
            raise HTTPException(
                status_code=451,
                detail="This file has been flagged as potentially malicious.",
            )
    except HTTPException:
        raise
    except Exception:
        logger.warning("Failed to check scan status for key=%s", key, exc_info=True)

    try:
        data, content_type = await async_download_file(key)
    except ClientError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")

    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
        },
    )


@router.get("/scan-status/{key:path}")
async def get_scan_status(
    key: str,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> dict:
    """Get VirusTotal scan status for a file."""
    if ".." in key or not _SAFE_KEY_RE.match(key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file key.",
        )

    scan = await file_scan_repo.find_by_key(key)
    if not scan:
        return {"status": "unknown", "positives": None, "total": None}

    return {
        "status": scan["status"],
        "positives": scan.get("positives"),
        "total": scan.get("total"),
    }


@router.get("/presigned/{key:path}")
async def get_presigned_url(
    key: str,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> dict:
    """Get a presigned download URL for a stored file.

    Admins can access any file. Editor files are accessible to any member.
    Other files require ownership.
    """
    if ".." in key or not _SAFE_KEY_RE.match(key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file key.",
        )

    is_admin = current_user["role"] in ("SUPER_ADMIN", "ADMIN")
    is_editor_file = key.startswith("editor/")
    owns_file = key.startswith(f"editor/{current_user['sub']}/") or key.startswith(
        f"avatars/{current_user['sub']}"
    )
    # Editor files are readable by any authenticated member
    if not is_admin and not is_editor_file and not owns_file:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this file.",
        )
    url = await async_presigned_url(key, expires_in=3600)
    return {"url": url, "key": key}
