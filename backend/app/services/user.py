import uuid

from fastapi import HTTPException, status
from loguru import logger

from app.core.async_storage import get_user_storage_used
from app.core.async_storage import upload_file as async_upload_file
from app.core.config import settings
from app.core.event_bus import emit
from app.core.file_validation import validate_avatar
from app.core.redis import get_redis
from app.core.security import async_hash_password, async_verify_password, validate_password_policy
from app.core.storage import generate_avatar_key
from app.models.user import UserRole
from app.repositories import user_repo


async def get_user_by_username(username: str) -> dict | None:
    return await user_repo.find_by_username(username)


async def get_user_by_id(user_id: uuid.UUID) -> dict | None:
    return await user_repo.find_by_id(user_id)


async def create_user(
    username: str,
    password: str,
    role: str = UserRole.MEMBER.value,
    display_name: str = "",
) -> dict:
    user_id = uuid.uuid4()
    pw_hash = await async_hash_password(password)
    if not display_name:
        display_name = username

    result = await user_repo.insert(user_id, username, pw_hash, role, display_name)
    logger.info("User created", extra={"user_id": str(user_id), "role": role})
    return result


async def update_user_profile(
    user_id: uuid.UUID,
    display_name: str | None = None,
    bio: str | None = None,
    affiliation: str | None = None,
    orcid: str | None = None,
    avatar_url: str | None = None,
    preferred_language: str | None = None,
) -> dict | None:
    return await user_repo.update_profile(
        user_id,
        display_name=display_name,
        bio=bio,
        affiliation=affiliation,
        orcid=orcid,
        avatar_url=avatar_url,
        preferred_language=preferred_language,
    )


async def upload_user_avatar(
    user_id: str,
    data: bytes,
    content_type: str,
    filename: str,
) -> dict:
    """Validate, upload, and persist a user avatar.

    Performs quota check, file validation, storage upload, and DB update.
    Returns the updated user dict.
    Raises HTTPException on validation/quota failure.
    """
    if not content_type:
        raise HTTPException(status_code=400, detail="File content type is required.")
    validate_avatar(content_type, data)

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
        used = await get_user_storage_used(user_id)
        if used + len(data) > settings.MAX_USER_STORAGE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Storage quota exceeded (1 GB limit).",
            )

        ext = ".png" if content_type == "image/png" else ".jpg"
        key = generate_avatar_key(user_id, ext)
        await async_upload_file(data, key, content_type)
    finally:
        await redis.delete(lock_key)

    # Store the MinIO object key (not presigned URL) — fresh URLs generated on read
    user = await update_user_profile(
        user_id=uuid.UUID(user_id),
        avatar_url=key,
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user


async def user_exists_by_username(username: str) -> bool:
    return await user_repo.exists_by_username(username)


async def update_user_role(user_id: uuid.UUID, new_role: str) -> dict | None:
    result = await user_repo.update_role(user_id, new_role)
    if result:
        logger.info("User role updated", extra={"user_id": str(user_id), "new_role": new_role})
    return result


async def anonymize_user(user_id: uuid.UUID) -> bool:
    """GDPR anonymization: overwrite PII, set is_deleted=true."""
    anon_name = f"Deleted_User_{uuid.uuid4().hex[:8]}"
    deleted = await user_repo.anonymize(user_id, anon_name)
    if deleted:
        logger.info("User anonymized (GDPR)", extra={"user_id": str(user_id)})
    return deleted


async def ban_user(user_id: uuid.UUID, reason: str) -> bool:
    """Ban a user: set is_banned=true, revoke all sessions, send WS FORCE_LOGOUT."""
    banned = await user_repo.set_ban(user_id, reason)
    if not banned:
        return False

    # Revoke all Redis sessions (lazy import to avoid circular dependency)
    from app.services.auth import revoke_user_sessions

    await revoke_user_sessions(str(user_id))

    # Force logout via WebSocket (best-effort, through event bus)
    await emit("user.banned", user_id=str(user_id))

    logger.info("User banned", extra={"user_id": str(user_id), "reason": reason})
    return True


async def unban_user(user_id: uuid.UUID) -> bool:
    """Unban a user: set is_banned=false, clear ban_reason."""
    unbanned = await user_repo.clear_ban(user_id)
    if unbanned:
        logger.info("User unbanned", extra={"user_id": str(user_id)})
    return unbanned


async def change_password(user_id: uuid.UUID, old_password: str, new_password: str) -> bool:
    """Verify old password, validate policy, hash new, update. Returns True on success."""
    pw_hash = await user_repo.find_password_hash(user_id)
    if not pw_hash:
        raise ValueError("User not found.")

    if not await async_verify_password(old_password, pw_hash):
        raise ValueError("Current password is incorrect.")

    error = validate_password_policy(new_password)
    if error:
        raise ValueError(error)

    new_hash = await async_hash_password(new_password)
    await user_repo.update_password_hash(user_id, new_hash)
    logger.info("Password changed", extra={"user_id": str(user_id)})
    return True


async def list_users(
    page: int = 1,
    page_size: int = 50,
    search: str | None = None,
) -> tuple[list[dict], int]:
    return await user_repo.list_all(page=page, page_size=page_size, search=search)


async def bulk_change_role(user_ids: list[uuid.UUID], role: str) -> int:
    """Change role for multiple users in a single transaction."""
    from app.core.database import get_pool

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            count = await user_repo.bulk_update_role(user_ids, role, conn)
    return count
