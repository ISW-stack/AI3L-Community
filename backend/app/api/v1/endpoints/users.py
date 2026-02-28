import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status

from app.core.deps import get_current_user, require_role
from app.core.security import validate_password_policy
from app.models.user import UserRole
from app.schemas.auth import MessageResponse
from app.schemas.user import (
    AdminCreateAccountRequest,
    BanRequest,
    RoleUpdateRequest,
    UserListResponse,
    UserResponse,
    UserUpdateRequest,
)
from app.services.auth import destroy_session
from app.services.user import (
    anonymize_user,
    ban_user,
    create_user,
    get_user_by_id,
    list_users,
    unban_user,
    update_user_profile,
    update_user_role,
    user_exists_by_username,
)

router = APIRouter(prefix="/users", tags=["users"])


def _resolve_avatar_url(avatar_url: str | None) -> str | None:
    """If avatar_url is a MinIO object key (no 'http'), generate a fresh presigned URL."""
    if not avatar_url:
        return None
    if avatar_url.startswith("http://") or avatar_url.startswith("https://"):
        return avatar_url
    try:
        from app.core.storage import generate_presigned_url

        return generate_presigned_url(avatar_url, expires_in=86400 * 7)  # 7-day URL
    except Exception:
        return avatar_url


def _user_to_response(user: dict) -> UserResponse:
    return UserResponse(
        id=str(user["id"]),
        username=user["username"],
        display_name=user["display_name"],
        role=user["role"],
        avatar_url=_resolve_avatar_url(user.get("avatar_url")),
        orcid=user.get("orcid"),
        affiliation=user.get("affiliation"),
        bio=user.get("bio"),
        is_banned=user.get("is_banned", False),
        ban_reason=user.get("ban_reason"),
    )


@router.get("/me", response_model=UserResponse)
async def get_my_profile(current_user: dict = Depends(get_current_user)) -> UserResponse:
    user = await get_user_by_id(uuid.UUID(current_user["sub"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return _user_to_response(user)


@router.put("/me", response_model=UserResponse)
async def update_my_profile(
    req: UserUpdateRequest,
    current_user: dict = Depends(get_current_user),
) -> UserResponse:
    user = await update_user_profile(
        user_id=uuid.UUID(current_user["sub"]),
        display_name=req.display_name,
        bio=req.bio,
        affiliation=req.affiliation,
        orcid=req.orcid,
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return _user_to_response(user)


@router.put("/me/avatar", response_model=UserResponse)
async def upload_avatar(
    file: UploadFile,
    current_user: dict = Depends(get_current_user),
) -> UserResponse:
    """Upload avatar image (PNG/JPEG, max 2MB)."""
    allowed_types = {"image/png", "image/jpeg"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PNG and JPEG images are allowed.",
        )

    data = await file.read()
    max_size = 2 * 1024 * 1024  # 2MB
    if len(data) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 2MB limit.",
        )

    # Storage quota check
    from app.core.config import settings as _settings
    from app.services.user import get_user_storage_used

    used = get_user_storage_used(current_user["sub"])
    if used + len(data) > _settings.MAX_USER_STORAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Storage quota exceeded (1 GB limit).",
        )

    from app.core.storage import generate_avatar_key, upload_file

    ext = ".png" if file.content_type == "image/png" else ".jpg"
    key = generate_avatar_key(current_user["sub"], ext)
    upload_file(data, key, file.content_type)

    # Store the MinIO object key (not presigned URL) — fresh URLs generated on read
    user = await update_user_profile(
        user_id=uuid.UUID(current_user["sub"]),
        avatar_url=key,
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return _user_to_response(user)


@router.post("/me/consent", response_model=MessageResponse)
async def accept_privacy_consent(
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> MessageResponse:
    """Record user's acceptance of the privacy consent."""
    ip = request.client.host if request.client else "unknown"
    user_id = current_user["sub"]
    role = current_user.get("role")

    if role == "GUEST":
        from app.services.privacy_consent import create_guest_consent

        await create_guest_consent(user_id)
    else:
        from app.services.privacy_consent import create_consent

        await create_consent(user_id, ip)

    return MessageResponse(message="Privacy consent recorded.")


@router.delete("/me", response_model=MessageResponse)
async def delete_my_account(
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> MessageResponse:
    """GDPR anonymization: overwrite PII and invalidate session."""
    user_id = uuid.UUID(current_user["sub"])
    deleted = await anonymize_user(user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    await destroy_session(current_user["sub"], current_user["role"], current_user["jti"])

    # Audit log (best-effort)
    try:
        from app.services.audit import log_action

        ip = request.client.host if request.client else None
        await log_action(current_user["sub"], "ACCOUNT_DELETE", target_type="user", target_id=current_user["sub"], ip_address=ip)
    except Exception:
        pass

    return MessageResponse(message="Account deleted and anonymized.")


# --- Admin endpoints ---


@router.get(
    "",
    response_model=UserListResponse,
)
async def get_all_users(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> UserListResponse:
    users, total = await list_users(offset=offset, limit=limit)
    return UserListResponse(users=[_user_to_response(u) for u in users], total=total)


@router.post(
    "/admin/create-account",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_account(
    req: AdminCreateAccountRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> UserResponse:
    error = validate_password_policy(req.password)
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    valid_roles = {UserRole.MEMBER.value, UserRole.ADMIN.value}
    if req.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role must be one of: {', '.join(valid_roles)}",
        )

    # Only SUPER_ADMIN can create ADMIN accounts
    if req.role == UserRole.ADMIN.value and current_user["role"] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can create Admin accounts.",
        )

    if await user_exists_by_username(req.username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists.")

    user = await create_user(
        username=req.username,
        password=req.password,
        role=req.role,
        display_name=req.display_name,
    )
    return _user_to_response(user)


@router.put("/{user_id}/role", response_model=UserResponse)
async def change_user_role(
    user_id: uuid.UUID,
    req: RoleUpdateRequest,
    request: Request,
    current_user: dict = Depends(require_role("SUPER_ADMIN")),
) -> UserResponse:
    valid_roles = {r.value for r in UserRole if r != UserRole.GUEST}
    if req.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role must be one of: {', '.join(valid_roles)}",
        )

    # Prevent self-demotion
    if str(user_id) == current_user["sub"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role.",
        )

    user = await update_user_role(user_id, req.role)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Revoke target user's existing sessions by deleting their Redis key
    from app.core.redis import get_redis

    redis = get_redis()
    for role in [r.value for r in UserRole]:
        await redis.delete(f"session:{role}:{user_id}")

    # Audit log (best-effort)
    try:
        from app.services.audit import log_action

        ip = request.client.host if request.client else None
        await log_action(current_user["sub"], "ROLE_CHANGE", target_type="user", target_id=str(user_id), ip_address=ip)
    except Exception:
        pass

    return _user_to_response(user)


@router.post("/{user_id}/ban", response_model=MessageResponse)
async def ban_user_endpoint(
    user_id: uuid.UUID,
    req: BanRequest,
    request: Request,
    current_user: dict = Depends(require_role("SUPER_ADMIN")),
) -> MessageResponse:
    """Ban a user: set is_banned=true, revoke all sessions, force logout via WS."""
    if str(user_id) == current_user["sub"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot ban yourself.",
        )

    result = await ban_user(user_id, req.reason)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Audit log (best-effort)
    try:
        from app.services.audit import log_action

        ip = request.client.host if request.client else None
        await log_action(current_user["sub"], "BAN", target_type="user", target_id=str(user_id), ip_address=ip)
    except Exception:
        pass

    return MessageResponse(message="User has been banned.")


@router.post("/{user_id}/unban", response_model=MessageResponse)
async def unban_user_endpoint(
    user_id: uuid.UUID,
    request: Request,
    current_user: dict = Depends(require_role("SUPER_ADMIN")),
) -> MessageResponse:
    """Unban a user: set is_banned=false, clear ban_reason."""
    result = await unban_user(user_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Audit log (best-effort)
    try:
        from app.services.audit import log_action

        ip = request.client.host if request.client else None
        await log_action(current_user["sub"], "UNBAN", target_type="user", target_id=str(user_id), ip_address=ip)
    except Exception:
        pass

    return MessageResponse(message="User has been unbanned.")


# --- Audit Logs (admin) ---


@router.get("/admin/audit-logs")
async def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user_id: str | None = None,
    current_user: dict = Depends(require_role("SUPER_ADMIN")),
) -> dict:
    from app.services.audit import list_audit_logs

    logs, total = await list_audit_logs(page=page, page_size=page_size, user_id_filter=user_id)
    return {"logs": logs, "total": total, "page": page, "page_size": page_size}
