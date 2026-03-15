import io
import re
import uuid

from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from loguru import logger

from app.core.async_storage import delete_file as async_delete_file
from app.core.async_storage import download_file as async_download_file
from app.core.async_storage import generate_presigned_url as async_presigned_url
from app.core.async_storage import get_file_size as async_get_file_size
from app.core.async_storage import upload_file as async_upload_file
from app.core.config import settings
from app.core.constants import MAX_EDITOR_FILE_SIZE, RATE_LIMIT_FILE_UPLOAD
from app.core.deps import require_role
from app.core.errors import AppError, ErrorCode
from app.core.file_validation import validate_editor_file
from app.core.rate_limit import check_rate_limit
from app.core.redis import get_redis
from app.repositories import file_scan_repo, user_repo
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
        raise AppError(ErrorCode.SYS_429, 429, "Too many uploads. Try again later.")
    filename = file.filename or "unnamed"
    data = await file.read(MAX_EDITOR_FILE_SIZE + 1)
    if len(data) > MAX_EDITOR_FILE_SIZE:
        raise AppError(ErrorCode.FILE_001, status.HTTP_400_BAD_REQUEST, "File size exceeds 20MB limit.")
    expected_type, data = await run_in_threadpool(validate_editor_file, filename, data)

    # Acquire per-user upload lock to prevent concurrent quota bypass
    redis = get_redis()
    lock_key = f"upload_lock:{user_id}"
    acquired = await redis.set(lock_key, "1", nx=True, ex=120)
    if not acquired:
        raise AppError(
            ErrorCode.SYS_429,
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Another upload is in progress. Please wait.",
        )

    try:
        # Storage quota check — read from DB (O(1)) instead of S3 LIST
        user_uuid = uuid.UUID(current_user["sub"])
        used = await user_repo.get_storage_used(user_uuid)
        if used + len(data) > settings.MAX_USER_STORAGE_BYTES:
            raise AppError(
                ErrorCode.SYS_422,
                status.HTTP_400_BAD_REQUEST,
                "Storage quota exceeded (1 GB limit).",
            )

        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        key = f"editor/{current_user['sub']}/{uuid.uuid4().hex}{ext}"
        await async_upload_file(data, key, expected_type)
        # Increment DB-tracked storage counter after successful upload.
        try:
            await user_repo.increment_storage_used(user_uuid, len(data))
        except Exception:
            logger.error(
                "Storage counter increment failed, rolling back upload for user=%s key=%s",
                current_user["sub"],
                key,
                exc_info=True,
            )
            try:
                await async_delete_file(key)
            except Exception:
                logger.error(
                    "Failed to rollback uploaded file after increment failure",
                    extra={"key": key},
                    exc_info=True,
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Upload failed. Please try again.",
            )
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

        file_hash = await run_in_threadpool(compute_sha256, io.BytesIO(data))
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


@router.delete("/content/{key:path}", status_code=status.HTTP_200_OK)
async def delete_editor_file(
    key: str,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> dict:
    """Delete an editor file from storage and decrement the user's storage counter."""
    if ".." in key or not _SAFE_KEY_RE.match(key):
        raise AppError(ErrorCode.SYS_422, status.HTTP_400_BAD_REQUEST, "Invalid file key.")

    # Only allow deletion of editor files owned by the user (or by admins)
    is_admin = current_user["role"] in ("SUPER_ADMIN", "ADMIN")
    owns_file = key.startswith(f"editor/{current_user['sub']}/")
    if not is_admin and not owns_file:
        raise AppError(
            ErrorCode.SYS_403,
            status.HTTP_403_FORBIDDEN,
            "You do not have permission to delete this file.",
        )

    # Get file size before deletion for storage decrement
    file_size = await async_get_file_size(key)
    if file_size == 0:
        raise AppError(ErrorCode.SYS_404, status.HTTP_404_NOT_FOUND, "File not found.")

    # Validate that the key is an editor file before parsing owner from path
    if not key.startswith("editor/"):
        raise AppError(
            ErrorCode.SYS_422,
            status.HTTP_400_BAD_REQUEST,
            "Only editor files can be deleted via this endpoint.",
        )

    # Determine the owner user ID from the key path (editor/{user_id}/...)
    parts = key.split("/")
    if len(parts) >= 2:
        owner_user_id = parts[1]
    else:
        raise AppError(
            ErrorCode.SYS_422, status.HTTP_400_BAD_REQUEST, "Invalid file key format."
        )

    # Delete the file from storage
    try:
        await async_delete_file(key)
    except Exception:
        logger.error("Failed to delete file from storage key=%s", key, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file from storage.",
        )

    # Decrement the owner's storage counter
    try:
        owner_uuid = uuid.UUID(owner_user_id)
        await user_repo.increment_storage_used(owner_uuid, -file_size)
    except Exception:
        logger.warning(
            "Failed to decrement storage counter for user=%s key=%s size=%d",
            owner_user_id,
            key,
            file_size,
            exc_info=True,
        )

    # Remove scan record if it exists
    try:
        await file_scan_repo.delete_by_key(key)
    except Exception:
        logger.warning("Failed to delete scan record for key=%s", key, exc_info=True)

    # Emit audit event for admin file deletions
    if is_admin and not owns_file:
        try:
            from app.core.event_bus import emit

            await emit(
                "audit.action",
                action="admin_file_delete",
                actor_id=current_user["sub"],
                target_key=key,
                file_size=file_size,
                owner_user_id=owner_user_id,
            )
        except Exception:
            logger.warning("Failed to emit audit event for file deletion", exc_info=True)

    return {"detail": "File deleted.", "key": key, "freed_bytes": file_size}


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
        raise AppError(ErrorCode.SYS_422, status.HTTP_400_BAD_REQUEST, "Invalid file key.")

    is_editor_file = key.startswith("editor/")
    is_admin = current_user["role"] in ("SUPER_ADMIN", "ADMIN")

    # Editor files are readable by any authenticated member (they're embedded in public posts)
    if not is_editor_file and not is_admin:
        owns_file = key.startswith(f"avatars/{current_user['sub']}")
        if not owns_file:
            raise AppError(
                ErrorCode.SYS_403,
                status.HTTP_403_FORBIDDEN,
                "You do not have permission to access this file.",
            )

    # Block files that are malicious, unverified, or had scan errors (fail-close)
    try:
        scan = await file_scan_repo.find_by_key(key)
        if scan and scan["status"] == "malicious":
            raise AppError(
                ErrorCode.FILE_001,
                451,
                "This file has been flagged as potentially malicious.",
            )
        if scan and scan["status"] in ("unknown", "error"):
            raise AppError(
                ErrorCode.FILE_001,
                status.HTTP_403_FORBIDDEN,
                "This file has not been verified as safe. Scan status: " + scan["status"],
            )
    except (HTTPException, AppError):
        raise
    except Exception:
        logger.warning("Failed to check scan status for key=%s", key, exc_info=True)

    try:
        data, content_type = await async_download_file(key)
    except ClientError:
        raise AppError(ErrorCode.SYS_404, status.HTTP_404_NOT_FOUND, "File not found.")

    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
        },
    )


@router.get("/storage-usage")
async def get_storage_usage(
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> dict[str, int]:
    """Return the current user's storage usage and quota in bytes (DB-tracked)."""
    used = await user_repo.get_storage_used(uuid.UUID(current_user["sub"]))
    return {
        "used_bytes": used,
        "quota_bytes": settings.MAX_USER_STORAGE_BYTES,
    }


@router.get("/scan-status/{key:path}")
async def get_scan_status(
    key: str,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> dict:
    """Get VirusTotal scan status for a file."""
    if ".." in key or not _SAFE_KEY_RE.match(key):
        raise AppError(ErrorCode.SYS_422, status.HTTP_400_BAD_REQUEST, "Invalid file key.")

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
        raise AppError(ErrorCode.SYS_422, status.HTTP_400_BAD_REQUEST, "Invalid file key.")

    is_admin = current_user["role"] in ("SUPER_ADMIN", "ADMIN")
    is_editor_file = key.startswith("editor/")
    owns_file = key.startswith(f"editor/{current_user['sub']}/") or key.startswith(
        f"avatars/{current_user['sub']}"
    )
    # Editor files are readable by any authenticated member
    if not is_admin and not is_editor_file and not owns_file:
        raise AppError(
            ErrorCode.SYS_403,
            status.HTTP_403_FORBIDDEN,
            "You do not have permission to access this file.",
        )
    url = await async_presigned_url(key, expires_in=3600)
    return {"url": url, "key": key}
