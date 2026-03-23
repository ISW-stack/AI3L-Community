import asyncio
import uuid
from datetime import date as DateType

from fastapi import APIRouter, Depends, Query, Request, Response, UploadFile, status

from app.converters.user_converter import async_user_to_public_response, async_user_to_response
from app.core.constants import MAX_AVATAR_SIZE
from app.core.deps import get_current_user, require_role
from app.core.errors import (
    AppError,
    ErrorCode,
    RateLimitError,
    ServiceNotFoundError,
    ServiceValidationError,
    StorageQuotaError,
)
from app.core.event_bus import emit
from app.core.file_validation import sanitize_html
from app.core.rate_limit import check_rate_limit
from app.core.security import validate_password_policy
from app.models.user import UserRole
from app.schemas.auth import MessageResponse
from app.schemas.user import (
    AdminCreateAccountRequest,
    AdminDeleteUserRequest,
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
    check_sole_admin_sigs,
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


@router.get("/me", response_model=UserResponse)
async def get_my_profile(current_user: dict = Depends(get_current_user)) -> UserResponse:
    user = await get_user_by_id(uuid.UUID(current_user["sub"]))
    if user is None:
        raise AppError(ErrorCode.SYS_404, 404, "User not found.")
    resp = await async_user_to_response(user)

    # Include preferences in response
    from app.services.preferences import get_user_preferences

    prefs = await get_user_preferences(uuid.UUID(current_user["sub"]))
    resp.preferences = prefs
    return resp


@router.put("/me", response_model=UserResponse)
async def update_my_profile(
    req: UserUpdateRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> UserResponse:
    # Only pass fields that the client explicitly included in the request.
    # This lets the backend distinguish "not provided" (omitted) from
    # "explicitly set to null" (user wants to clear the field).
    provided = {
        k: getattr(req, k)
        for k in ("display_name", "bio", "affiliation", "orcid", "preferred_language")
        if k in req.model_fields_set
    }
    # Sanitize bio HTML like post content
    if "bio" in provided and provided["bio"]:
        provided["bio"] = sanitize_html(provided["bio"])
    try:
        user = await update_user_profile(
            user_id=uuid.UUID(current_user["sub"]),
            **provided,
        )
    except ValueError as e:
        raise AppError(ErrorCode.SYS_422, 400, str(e))
    if user is None:
        raise AppError(ErrorCode.SYS_404, 404, "User not found.")
    return await async_user_to_response(user)


@router.put("/me/avatar", response_model=UserResponse)
async def upload_avatar(
    file: UploadFile,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> UserResponse:
    """Upload avatar image (PNG/JPEG, max 2MB)."""
    data = await file.read(MAX_AVATAR_SIZE + 1)
    if len(data) > MAX_AVATAR_SIZE:
        raise AppError(ErrorCode.SYS_422, 400, "File size exceeds 2MB limit.")
    try:
        user = await upload_user_avatar(
            user_id=current_user["sub"],
            data=data,
            content_type=file.content_type or "",
            filename=file.filename or "",
        )
    except ServiceValidationError as e:
        raise AppError(ErrorCode.SYS_422, 400, str(e))
    except StorageQuotaError as e:
        raise AppError(ErrorCode.SYS_422, 400, str(e))
    except RateLimitError as e:
        raise AppError(ErrorCode.SYS_429, 429, str(e))
    except ServiceNotFoundError as e:
        raise AppError(ErrorCode.SYS_404, 404, str(e))
    return await async_user_to_response(user)


@router.put("/me/password", response_model=MessageResponse)
async def change_my_password(
    request: Request,
    response: Response,
    req: ChangePasswordRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> MessageResponse:
    """Change password: verify current, validate new, update, destroy session."""
    if not await check_rate_limit(f"rl:password_change:{current_user['sub']}", 5, 300):
        raise AppError(
            ErrorCode.SYS_429, 429, "Too many password change attempts. Try again later."
        )
    try:
        await change_password(
            user_id=uuid.UUID(current_user["sub"]),
            old_password=req.current_password,
            new_password=req.new_password,
        )
    except ValueError as e:
        msg = str(e)
        # Only pass through known safe error prefixes from validate_password_policy
        if not any(
            msg.startswith(prefix) for prefix in ("Password ", "Current ", "New ", "Incorrect ")
        ):
            msg = "Invalid input."
        raise AppError(ErrorCode.SYS_422, 400, msg)

    # Audit log (best-effort, via event bus)
    ip = request.client.host if request.client else None
    await emit("audit.action", user_id=current_user["sub"], action="PASSWORD_CHANGE", ip_address=ip)

    # Revoke ALL sessions (all devices) so user must re-login everywhere
    await revoke_user_sessions(current_user["sub"])

    # Clear auth cookies so this client is immediately logged out
    from app.core.config import settings

    domain = settings.COOKIE_DOMAIN if settings.COOKIE_DOMAIN else None
    response.delete_cookie(key="access_token", path="/", domain=domain)
    response.delete_cookie(key="csrf_token", path="/", domain=domain)

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
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> MessageResponse:
    """GDPR anonymization: overwrite PII and invalidate session."""
    user_id = uuid.UUID(current_user["sub"])

    # Block deletion if the user is the sole admin of any SIG
    sole_admin_sigs = await check_sole_admin_sigs(user_id)
    if sole_admin_sigs:
        sig_names = ", ".join(s["name"] for s in sole_admin_sigs)
        raise AppError(
            ErrorCode.SYS_409,
            409,
            (
                "Cannot delete account: you are the sole admin of the following SIG(s): "
                f"{sig_names}. Please assign another admin before deleting your account."
            ),
        )

    result = await anonymize_user(user_id)
    if not result["anonymized"]:
        raise AppError(ErrorCode.SYS_404, 404, "User not found.")

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

    msg = "Account deleted and anonymized."
    if not result.get("cleanup_succeeded", True):
        msg += " Warning: some related data cleanup failed; an administrator has been notified."
    return MessageResponse(message=msg)


@router.get("/search")
async def search_users(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(5, ge=1, le=20),
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> list[dict]:
    """Search users by display name or username for co-author invitation."""
    from app.converters.user_converter import async_resolve_avatar_url
    from app.core.blacklist import get_blocked_user_ids
    from app.core.database import get_pool
    from app.core.redis import get_redis
    from app.repositories.user_repo import search_users_for_coauthor

    # Fetch blocked user IDs to exclude from results
    exclude_ids: set[str] = set()
    try:
        redis = get_redis()
        pool = get_pool()
        exclude_ids = await get_blocked_user_ids(redis, current_user["sub"], pool=pool)
    except Exception:
        pass  # Redis/DB failure → don't filter

    rows = await search_users_for_coauthor(q, limit, exclude_ids=exclude_ids)

    return [
        {
            "id": str(r["id"]),
            "username": r["username"],
            "display_name": r["display_name"],
            "avatar_url": await async_resolve_avatar_url(r.get("avatar_url")),
        }
        for r in rows
    ]


@router.get("/me/co-author-invitations")
async def get_my_co_author_invitations(
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> dict:
    """List pending co-author invitations for the current user."""
    from app.services.co_author import list_pending_invitations

    invitations, total = await list_pending_invitations(
        user_id=current_user["sub"], page=page, page_size=page_size
    )
    return {"invitations": invitations, "total": total}


@router.put("/me/co-author-invitations/{invitation_id}/accept")
async def accept_co_author_invitation(
    invitation_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> dict:
    """Accept a co-author invitation."""
    from app.services.co_author import respond_to_invitation

    await respond_to_invitation(
        co_author_id=invitation_id, user_id=current_user["sub"], accept=True
    )
    return {"message": "Invitation accepted."}


@router.put("/me/co-author-invitations/{invitation_id}/reject")
async def reject_co_author_invitation(
    invitation_id: uuid.UUID,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN", "MEMBER")),
) -> dict:
    """Reject a co-author invitation."""
    from app.services.co_author import respond_to_invitation

    await respond_to_invitation(
        co_author_id=invitation_id, user_id=current_user["sub"], accept=False
    )
    return {"message": "Invitation rejected."}


@router.put("/bulk-role", status_code=status.HTTP_200_OK)
async def bulk_change_role(
    req: BulkRoleChangeRequest,
    current_user: dict = Depends(require_role("SUPER_ADMIN")),
) -> dict:
    from app.services.audit import log_action
    from app.services.user import bulk_change_role as bulk_change_role_svc

    count = await bulk_change_role_svc(req.user_ids, req.role, caller_role=current_user["role"])

    # Revoke sessions and notify each affected user (same as single role change)
    from app.services.auth import revoke_user_sessions

    for uid in req.user_ids:
        await emit("user.role_changed", user_id=str(uid), new_role=req.role)
        await revoke_user_sessions(str(uid))

    await log_action(
        user_id=current_user["sub"],
        action="BULK_ROLE_CHANGE",
        target_type="user",
        target_id=f"role={req.role},count={count}",
    )
    return {"updated_count": count}


@router.get("/my-application")
async def get_my_application_status(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Return the guest's most recent membership application, if any."""
    if current_user["role"] != "GUEST":
        raise AppError(ErrorCode.AUTH_003, 403, "Only guests can view application status.")
    from app.schemas.application import MyApplicationResponse
    from app.services.application import get_my_application

    app = await get_my_application(uuid.UUID(current_user["sub"]))
    if app is None:
        return MyApplicationResponse(application=None).model_dump()
    return MyApplicationResponse(
        application=MyApplicationResponse.Item(
            id=str(app["id"]),
            status=app["status"],
            created_at=app["created_at"].isoformat(),
            reviewed_at=app["reviewed_at"].isoformat() if app.get("reviewed_at") else None,
        )
    ).model_dump()


@router.delete("/{user_id}", response_model=MessageResponse)
async def admin_delete_user(
    user_id: uuid.UUID,
    request: Request,
    req: AdminDeleteUserRequest = AdminDeleteUserRequest(reason=""),
    current_user: dict = Depends(require_role("SUPER_ADMIN")),
) -> MessageResponse:
    """SUPER_ADMIN soft-deletes (anonymizes) another user."""
    if str(user_id) == current_user["sub"]:
        raise AppError(ErrorCode.SYS_422, 400, "Cannot delete yourself.")

    target = await get_user_by_id(user_id)
    if target is None:
        raise AppError(ErrorCode.SYS_404, 404, "User not found.")

    if target.get("role") == "SUPER_ADMIN":
        raise AppError(ErrorCode.SYS_403, 403, "Cannot delete a Super Admin.")

    # Block deletion if the target user is the sole admin of any SIG
    sole_admin_sigs = await check_sole_admin_sigs(user_id)
    if sole_admin_sigs:
        sig_names = ", ".join(s["name"] for s in sole_admin_sigs)
        raise AppError(
            ErrorCode.SYS_409,
            409,
            (
                "Cannot delete user: they are the sole admin of the following SIG(s): "
                f"{sig_names}. Please assign another admin first."
            ),
        )

    result = await anonymize_user(user_id)
    if not result["anonymized"]:
        raise AppError(ErrorCode.SYS_404, 404, "User not found.")

    # Revoke the target user's sessions
    await revoke_user_sessions(str(user_id))

    # Audit log
    ip = request.client.host if request.client else None
    await emit(
        "audit.action",
        user_id=current_user["sub"],
        action="ADMIN_DELETE_USER",
        target_type="user",
        target_id=str(user_id),
        ip_address=ip,
        detail=req.reason or None,
    )

    msg = "User has been deleted and anonymized."
    if not result.get("cleanup_succeeded", True):
        msg += " Warning: some related data cleanup failed; check server logs."
    return MessageResponse(message=msg)


@router.get("/{user_id}", response_model=PublicUserResponse)
async def get_public_profile(
    user_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
) -> PublicUserResponse:
    user = await get_user_by_id(user_id)
    if user is None or user.get("is_deleted", False):
        raise AppError(ErrorCode.SYS_404, 404, "User not found.")

    # Block check: if viewer has blocked this user or vice versa, return 404
    try:
        from app.core.blacklist import get_blocked_user_ids
        from app.core.redis import get_redis

        redis = get_redis()
        blocked_ids = await get_blocked_user_ids(redis, current_user["sub"])
        if str(user_id) in blocked_ids:
            raise AppError(ErrorCode.SYS_404, 404, "User not found.")
    except AppError:
        raise
    except Exception:
        pass  # Redis failure → show profile

    # Record profile view (best-effort)
    try:
        from app.services.profile_view import record_profile_view

        await record_profile_view(None, None, str(user_id), current_user["sub"])
    except Exception:
        pass  # Best-effort, don't fail the request

    return await async_user_to_public_response(user)


# --- Admin endpoints ---


@router.get(
    "",
    response_model=UserListResponse,
)
async def get_all_users(
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(50, ge=1, le=100),
    search: str | None = Query(None, max_length=200),
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> UserListResponse:
    users, total = await list_users(page=page, page_size=page_size, search=search)
    user_responses = list(await asyncio.gather(*[async_user_to_response(u) for u in users]))
    return UserListResponse(users=user_responses, total=total)


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
        raise AppError(ErrorCode.SYS_422, 400, error)

    valid_roles = {UserRole.MEMBER.value, UserRole.ADMIN.value}
    if req.role not in valid_roles:
        raise AppError(ErrorCode.SYS_422, 400, f"Role must be one of: {', '.join(valid_roles)}")

    # Only SUPER_ADMIN can create ADMIN accounts
    if req.role == UserRole.ADMIN.value and current_user["role"] != UserRole.SUPER_ADMIN.value:
        raise AppError(ErrorCode.SYS_403, 403, "Only Super Admin can create Admin accounts.")

    if await user_exists_by_username(req.username):
        raise AppError(ErrorCode.SYS_409, 409, "Username already exists.")

    user = await create_user(
        username=req.username,
        password=req.password,
        role=req.role,
        display_name=req.display_name,
    )
    return await async_user_to_response(user)


@router.put("/{user_id}/role", response_model=UserResponse)
async def change_user_role(
    user_id: uuid.UUID,
    req: RoleUpdateRequest,
    request: Request,
    current_user: dict = Depends(require_role("SUPER_ADMIN")),
) -> UserResponse:
    valid_roles = {r.value for r in UserRole if r != UserRole.GUEST}
    if req.role not in valid_roles:
        raise AppError(ErrorCode.SYS_422, 400, f"Role must be one of: {', '.join(valid_roles)}")

    # Prevent self-demotion
    if str(user_id) == current_user["sub"]:
        raise AppError(ErrorCode.SYS_422, 400, "Cannot change your own role.")

    try:
        user = await update_user_role(user_id, req.role)
    except ValueError as e:
        raise AppError(ErrorCode.SYS_422, 400, str(e))
    if user is None:
        raise AppError(ErrorCode.SYS_404, 404, "User not found.")

    # Notify target user about role change via WebSocket
    await emit(
        "user.role_changed",
        user_id=str(user_id),
        new_role=req.role,
    )

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

    return await async_user_to_response(user)


@router.post("/{user_id}/ban", response_model=MessageResponse)
async def ban_user_endpoint(
    user_id: uuid.UUID,
    req: BanRequest,
    request: Request,
    current_user: dict = Depends(require_role("SUPER_ADMIN")),
) -> MessageResponse:
    """Ban a user: set is_banned=true, revoke all sessions, force logout via WS."""
    if str(user_id) == current_user["sub"]:
        raise AppError(ErrorCode.SYS_422, 400, "Cannot ban yourself.")

    result = await ban_user(user_id, req.reason)
    if not result:
        raise AppError(ErrorCode.SYS_404, 404, "User not found.")

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
        raise AppError(ErrorCode.SYS_404, 404, "User not found.")

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
    page: int = Query(1, ge=1, le=1000),
    page_size: int = Query(20, ge=1, le=50),
    user_id: str | None = None,
    date_from: DateType | None = Query(None),
    date_to: DateType | None = Query(None),
    current_user: dict = Depends(require_role("SUPER_ADMIN")),
) -> dict:
    if date_from and date_to and date_from > date_to:
        raise AppError(ErrorCode.SYS_422, 422, "date_from must not be after date_to.")
    logs, total = await list_audit_logs(
        page=page,
        page_size=page_size,
        user_id_filter=user_id,
        date_from=date_from,
        date_to=date_to,
    )
    return {"logs": logs, "total": total, "page": page, "page_size": page_size}
