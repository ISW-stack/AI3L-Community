import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.core.deps import require_role
from app.core.errors import AppError, ErrorCode
from app.core.file_validation import (
    MAX_EDITOR_FILE_SIZE,
    get_content_type_from_extension,
    sanitize_pdf,
    validate_magic_number,
)
from app.core.storage import generate_presigned_url, upload_file
from app.schemas.file import FileUploadResponse

router = APIRouter(prefix="/files", tags=["files"])

_SAFE_KEY_RE = re.compile(r"^[a-zA-Z0-9/_.\-]+$")


@router.post("/upload/editor", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_editor_file(
    file: UploadFile,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> FileUploadResponse:
    """Upload file for rich text editor (PNG, JPEG, PDF, DOCX). Max 20MB."""
    filename = file.filename or "unnamed"
    expected_type = get_content_type_from_extension(filename)
    if expected_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File type not allowed. Accepted: .png, .jpg, .jpeg, .pdf, .docx",
        )

    data = await file.read()
    if len(data) > MAX_EDITOR_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 20MB limit.",
        )

    if not validate_magic_number(data, expected_type):
        raise AppError(ErrorCode.FILE_001, 400, "File content does not match its extension (invalid magic number).")

    # Sanitize PDFs
    if expected_type == "application/pdf":
        data = sanitize_pdf(data)

    # Storage quota check
    from app.core.config import settings as _settings
    from app.services.user import get_user_storage_used

    used = get_user_storage_used(current_user["sub"])
    if used + len(data) > _settings.MAX_USER_STORAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Storage quota exceeded (1 GB limit).",
        )

    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    key = f"editor/{current_user['sub']}/{uuid.uuid4().hex}{ext}"
    upload_file(data, key, expected_type)
    url = generate_presigned_url(key, expires_in=86400 * 7)

    # Fire-and-forget VirusTotal check
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
    owns_file = key.startswith(f"editor/{current_user['sub']}/") or key.startswith(f"avatars/{current_user['sub']}")
    if not is_admin and not owns_file:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this file.",
        )
    url = generate_presigned_url(key, expires_in=3600)
    return {"url": url, "key": key}
