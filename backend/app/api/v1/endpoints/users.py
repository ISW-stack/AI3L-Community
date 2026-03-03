import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status

from app.converters.user_converter import user_to_public_response, user_to_response
from app.core.constants import MAX_AVATAR_SIZE
from app.core.deps import get_current_user, require_role
from app.core.event_bus import emit
from app.core.security import validate_password_policy
from app.models.user import UserRole
from app.schemas.auth import MessageResponse
from app.core.database import get_pool
from app.repositories import user_repo
from app.schemas.user import (
    AdminCreateAccountRequest,
    BanRequest,
    BulkRoleChangeRequest,
    ChangePasswordRequest,
    PublicUserResponse,
    RoleUpdateRequest,
    UserListResponse,
    UserResponse,
    UserUpdateRequest,
)
from app.services.audit import list_audit_logs
from app.services.auth import revoke_user_sessions
from app.services.privacy_consent import create_consent, create_guest_consent
from app.services.user import (
    anonymize_user,
    ban_user,
    change_password,
    create_user,
    get_user_by_id,
    list_users,
    unban_user,
    update_user_profile,
    update_user_role,
    upload_user_avatar,
    user_exists_by_username,
)

router = APIRouter(prefix="/users", tags=["users"])


_user_to_response = user_to_response


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
    data = await file.read(MAX_AVATAR_SIZE + 1)
    if len(data) > MAX_AVATAR_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 2MB limit.",
        )
    user = await upload_user_avatar(
        user_id=current_user["sub"],
        data=data,
        content_type=file.content_type or "",
        filename=file.filename or "",
    )
    return _user_to_response(user)


@router.put("/me/password", response_model=MessageResponse)
async def change_my_password(
    req: ChangePasswordRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> MessageResponse:
    """Change password: verify current, validate new, update, destroy session."""
    try:
        await change_password(
            user_id=uuid.UUID(current_user["sub"]),
            old_password=req.current_password,
            new_password=req.new_password,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Revoke ALL sessions (all devices) so user must re-login everywhere
    await revoke_user_sessions(current_user["sub"])
    return MessageResponse(message="Password changed successfully. Please log in again.")


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
        await create_guest_consent(user_id)
    else:
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

    # Revoke ALL sessions (all devices), not just the current one
    await revoke_user_sessions(current_user["sub"])

    # Audit log (best-effort, via event bus)
    ip = request.client.host if request.client else None
    await emit(
        "audit.action",
        user_id=current_user["sub"],
        action="ACCOUNT_DELETE",
        target_type="user",
        target_id=current_user["sub"],
        ip_address=ip,
    )

    return MessageResponse(message="Account deleted and anonymized.")


@router.get("/{user_id}", response_model=PublicUserResponse)
async def get_public_profile(
    user_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
) -> PublicUserResponse:
    user = await get_user_by_id(user_id)
    if user is None or user.get("is_deleted", False):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user_to_public_response(user)


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

    # Revoke target user's existing sessions
    await revoke_user_sessions(str(user_id))

    # Audit log (best-effort, via event bus)
    ip = request.client.host if request.client else None
    await emit(
        "audit.action",
        user_id=current_user["sub"],
        action="ROLE_CHANGE",
        target_type="user",
        target_id=str(user_id),
        ip_address=ip,
    )

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

    # Audit log (best-effort, via event bus)
    ip = request.client.host if request.client else None
    await emit(
        "audit.action",
        user_id=current_user["sub"],
        action="BAN",
        target_type="user",
        target_id=str(user_id),
        ip_address=ip,
    )

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

    # Audit log (best-effort, via event bus)
    ip = request.client.host if request.client else None
    await emit(
        "audit.action",
        user_id=current_user["sub"],
        action="UNBAN",
        target_type="user",
        target_id=str(user_id),
        ip_address=ip,
    )

    return MessageResponse(message="User has been unbanned.")


# --- Audit Logs (admin) ---


@router.get("/admin/audit-logs")
async def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    current_user: dict = Depends(require_role("SUPER_ADMIN")),
) -> dict:
    logs, total = await list_audit_logs(
        page=page,
        page_size=page_size,
        user_id_filter=user_id,
        date_from=date_from,
        date_to=date_to,
    )
    return {"logs": logs, "total": total, "page": page, "page_size": page_size}


@router.put("/bulk-role", status_code=status.HTTP_200_OK)
async def bulk_change_role(
    req: BulkRoleChangeRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN")),
):
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            count = await user_repo.bulk_update_role(req.user_ids, req.role, conn)
    from app.services.audit import log_action

    await log_action(
        user_id=current_user["sub"],
        action="BULK_ROLE_CHANGE",
        target_type="user",
        target_id=f"role={req.role},count={count}",
    )
    return {"updated_count": count}
