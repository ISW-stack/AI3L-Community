import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.core.deps import get_current_user, require_role
from app.core.security import validate_password_policy
from app.models.user import UserRole
from app.schemas.auth import MessageResponse
from app.schemas.user import (
    AdminCreateAccountRequest,
    RoleUpdateRequest,
    UserListResponse,
    UserResponse,
    UserUpdateRequest,
)
from app.services.auth import destroy_session
from app.services.user import (
    anonymize_user,
    create_user,
    get_user_by_id,
    list_users,
    update_user_profile,
    update_user_role,
    user_exists_by_username,
)

router = APIRouter(prefix="/users", tags=["users"])


def _user_to_response(user: dict) -> UserResponse:
    return UserResponse(
        id=str(user["id"]),
        username=user["username"],
        display_name=user["display_name"],
        role=user["role"],
        avatar_url=user.get("avatar_url"),
        orcid=user.get("orcid"),
        affiliation=user.get("affiliation"),
        bio=user.get("bio"),
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

    from app.core.storage import generate_avatar_key, generate_presigned_url, upload_file

    ext = ".png" if file.content_type == "image/png" else ".jpg"
    key = generate_avatar_key(current_user["sub"], ext)
    upload_file(data, key, file.content_type)

    avatar_url = generate_presigned_url(key, expires_in=86400 * 7)  # 7-day URL
    user = await update_user_profile(
        user_id=uuid.UUID(current_user["sub"]),
        avatar_url=avatar_url,
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return _user_to_response(user)


@router.delete("/me", response_model=MessageResponse)
async def delete_my_account(current_user: dict = Depends(get_current_user)) -> MessageResponse:
    """GDPR anonymization: overwrite PII and invalidate session."""
    user_id = uuid.UUID(current_user["sub"])
    deleted = await anonymize_user(user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    await destroy_session(current_user["sub"], current_user["role"], current_user["jti"])
    return MessageResponse(message="Account deleted and anonymized.")


# --- Admin endpoints ---


@router.get(
    "",
    response_model=UserListResponse,
)
async def get_all_users(
    offset: int = 0,
    limit: int = 50,
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
    old_role = user.get("role", req.role)
    # Try to delete sessions for all possible roles
    for role in [r.value for r in UserRole]:
        await redis.delete(f"session:{role}:{user_id}")

    return _user_to_response(user)
