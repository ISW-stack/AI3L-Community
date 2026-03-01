import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.core.async_storage import (
    generate_presigned_url as async_presigned_url,
    get_user_storage_used,
    upload_file as async_upload_file,
)
from app.core.config import settings
from app.core.deps import require_role
from app.core.file_validation import validate_editor_file
from app.core.storage import generate_presigned_url
from app.schemas.file import FileUploadResponse

router = APIRouter(prefix="/files", tags=["files"])

_SAFE_KEY_RE = re.compile(r"^[a-zA-Z0-9/_.\-]+$")


@router.post(
    "/upload/editor", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED
)
async def upload_editor_file(
    file: UploadFile,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> FileUploadResponse:
    """Upload file for rich text editor (PNG, JPEG, PDF, DOCX). Max 20MB."""
    filename = file.filename or "unnamed"
    data = await file.read()
    expected_type, data = validate_editor_file(filename, data)

    # Storage quota check
    used = await get_user_storage_used(current_user["sub"])
    if used + len(data) > settings.MAX_USER_STORAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Storage quota exceeded (1 GB limit).",
        )

    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    key = f"editor/{current_user['sub']}/{uuid.uuid4().hex}{ext}"
    await async_upload_file(data, key, expected_type)
    url = await async_presigned_url(key, expires_in=86400 * 7)

    # Fire-and-forget VirusTotal check (lazy import to avoid celery dependency at module load)
    try:
        from app.tasks.virustotal import check_virustotal, compute_sha256

        file_hash = compute_sha256(data)
        check_virustotal.delay(file_hash, key)
    except Exception:
        pass  # Non-critical: don't block upload

    return FileUploadResponse(
        key=key,
        url=url,
        filename=filename,
        content_type=expected_type,
        size=len(data),
    )


@router.get("/presigned/{key:path}")
async def get_presigned_url(
    key: str,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> dict:
    """Get a presigned download URL for a stored file.

    Admins can access any file. Members can only access their own uploads.
    """
    if ".." in key or not _SAFE_KEY_RE.match(key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file key.",
        )

    is_admin = current_user["role"] in ("SUPER_ADMIN", "ADMIN")
    owns_file = key.startswith(f"editor/{current_user['sub']}/") or key.startswith(
        f"avatars/{current_user['sub']}"
    )
    if not is_admin and not owns_file:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this file.",
        )
    url = generate_presigned_url(key, expires_in=3600)
    return {"url": url, "key": key}
