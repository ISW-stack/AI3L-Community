import uuid

from loguru import logger

from app.core.async_storage import delete_file as async_delete_file
from app.core.async_storage import get_file_size as async_get_file_size
from app.core.async_storage import upload_file as async_upload_file
from app.core.config import settings
from app.core.errors import (
    RateLimitError,
    ServiceNotFoundError,
    ServiceValidationError,
    StorageQuotaError,
)
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


_PROFILE_FIELD_LIMITS: dict[str, int] = {
    "display_name": 100,
    "bio": 500,
    "affiliation": 200,
    "orcid": 30,
}


def _validate_profile_field_lengths(**fields: str | None) -> None:
    """Raise ValueError if any profile field exceeds its maximum length."""
    for name, value in fields.items():
        if value is not None and name in _PROFILE_FIELD_LIMITS:
            limit = _PROFILE_FIELD_LIMITS[name]
            if len(value) > limit:
                raise ValueError(f"{name} must be at most {limit} characters (got {len(value)}).")


async def update_user_profile(
    user_id: uuid.UUID,
    display_name: str | None = None,
    bio: str | None = None,
    affiliation: str | None = None,
    orcid: str | None = None,
    avatar_url: str | None = None,
    preferred_language: str | None = None,
) -> dict | None:
    _validate_profile_field_lengths(
        display_name=display_name,
        bio=bio,
        affiliation=affiliation,
        orcid=orcid,
    )
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
    Decrements storage for the old avatar before incrementing for the new one.
    Returns the updated user dict.
    Raises ServiceValidationError, StorageQuotaError, RateLimitError, or ServiceNotFoundError.
    """
    if not content_type:
        raise ServiceValidationError("File content type is required.")
    validate_avatar(content_type, data)

    # Acquire per-user upload lock to prevent concurrent quota bypass
    redis = get_redis()
    lock_key = f"upload_lock:{user_id}"
    acquired = await redis.set(lock_key, "1", nx=True, ex=120)
    if not acquired:
        raise RateLimitError("Another upload is in progress. Please wait.")

    user_uuid = uuid.UUID(user_id)
    try:
        # Get old avatar key and size for storage decrement
        old_avatar_size = 0
        existing_user = await user_repo.find_by_id(user_uuid)
        if existing_user:
            old_avatar_key = existing_user.get("avatar_url") or ""
            # Only attempt size lookup for MinIO keys (not http URLs)
            if old_avatar_key and not old_avatar_key.startswith(("http://", "https://")):
                try:
                    old_avatar_size = await async_get_file_size(old_avatar_key)
                except Exception:
                    logger.warning(
                        "Failed to get old avatar size for user=%s key=%s",
                        user_id,
                        old_avatar_key,
                        exc_info=True,
                    )

        # Storage quota check — read from DB (O(1)) instead of S3 LIST
        used = await user_repo.get_storage_used(user_uuid)
        # Account for the old avatar being replaced when checking quota
        effective_used = max(0, used - old_avatar_size)
        if effective_used + len(data) > settings.MAX_USER_STORAGE_BYTES:
            raise StorageQuotaError("Storage quota exceeded (1 GB limit).")

        ext = ".png" if content_type == "image/png" else ".jpg"
        key = generate_avatar_key(user_id, ext)
        await async_upload_file(data, key, content_type)
        # Update DB-tracked storage counter: net delta = new_size - old_size.
        # GREATEST(0, ...) in SQL prevents negative totals.
        net_delta = len(data) - old_avatar_size
        try:
            await user_repo.increment_storage_used(user_uuid, net_delta)
        except Exception:
            logger.error(
                "Failed to update storage counter for user=%s key=%s — "
                "attempting rollback by deleting uploaded file",
                user_id,
                key,
                exc_info=True,
            )
            try:
                await async_delete_file(key)
                logger.info(
                    "Rollback: deleted uploaded avatar after storage counter failure",
                    extra={"user_id": user_id, "key": key},
                )
            except Exception:
                logger.error(
                    "Rollback failed: could not delete uploaded avatar after "
                    "storage counter failure for user=%s key=%s",
                    user_id,
                    key,
                    exc_info=True,
                )
    finally:
        await redis.delete(lock_key)

    # Store the MinIO object key (not presigned URL) — fresh URLs generated on read
    user = await update_user_profile(
        user_id=uuid.UUID(user_id),
        avatar_url=key,
    )
    if user is None:
        raise ServiceNotFoundError("User not found.")

    # Delete old avatar file from MinIO after successful replacement
    if existing_user:
        old_avatar_key = existing_user.get("avatar_url") or ""
        if old_avatar_key and not old_avatar_key.startswith(("http://", "https://")):
            try:
                await async_delete_file(old_avatar_key)
            except Exception:
                logger.warning(
                    "Failed to delete old avatar for user=%s key=%s",
                    user_id,
                    old_avatar_key,
                    exc_info=True,
                )

    return user


async def user_exists_by_username(username: str) -> bool:
    return await user_repo.exists_by_username(username)


async def update_user_role(user_id: uuid.UUID, new_role: str) -> dict | None:
    # Prevent orphaning the system by demoting the last SUPER_ADMIN
    if new_role != "SUPER_ADMIN":
        current = await user_repo.find_by_id(user_id)
        if current and current["role"] == "SUPER_ADMIN":
            count = await user_repo.count_by_role("SUPER_ADMIN")
            if count <= 1:
                raise ValueError("Cannot demote: this is the last Super Admin in the system.")

    result = await user_repo.update_role(user_id, new_role)
    if result:
        logger.info("User role updated", extra={"user_id": str(user_id), "new_role": new_role})
    return result


async def check_sole_admin_sigs(user_id: uuid.UUID) -> list[dict]:
    """Return list of SIGs where the user is the sole admin.

    Used to block account deletion when it would orphan a SIG.
    """
    from app.repositories import sig_repo

    return await sig_repo.find_sole_admin_sigs(user_id)


async def anonymize_user(user_id: uuid.UUID) -> bool:
    """GDPR anonymization: overwrite PII, set is_deleted=true, clean up related data."""
    from app.core.database import get_pool

    anon_name = f"Deleted_User_{uuid.uuid4().hex[:8]}"
    deleted = await user_repo.anonymize(user_id, anon_name)
    if deleted:
        logger.info("User anonymized (GDPR)", extra={"user_id": str(user_id)})

        # Clean up all related data in dependency-safe order
        pool = get_pool()
        async with pool.acquire() as conn:
            try:
                async with conn.transaction():
                    from app.repositories import co_author_repo, profile_view_repo, vote_repo

                    # Citations (depends on posts)
                    await conn.execute(
                        "DELETE FROM post_citations WHERE citing_post_id IN "
                        "(SELECT id FROM posts WHERE user_id = $1)",
                        user_id,
                    )
                    await conn.execute(
                        "DELETE FROM post_citations WHERE cited_post_id IN "
                        "(SELECT id FROM posts WHERE user_id = $1)",
                        user_id,
                    )

                    # Co-authors
                    await co_author_repo.delete_by_user_id(conn, user_id)

                    # Profile views
                    await profile_view_repo.delete_by_profile_or_viewer(conn, user_id)

                    # Comment votes
                    await vote_repo.delete_by_user_id(conn, user_id)

                    # Notifications (user as recipient or trigger)
                    await conn.execute(
                        "DELETE FROM notifications WHERE user_id = $1 OR trigger_user_id = $1",
                        user_id,
                    )

                    # Form responses
                    await conn.execute(
                        "DELETE FROM form_responses WHERE user_id = $1",
                        user_id,
                    )

                    # Friend recommendations and dismissed recommendations
                    await conn.execute(
                        "DELETE FROM friend_recommendations WHERE user_id = $1 OR recommended_user_id = $1",
                        user_id,
                    )
                    await conn.execute(
                        "DELETE FROM dismissed_recommendations WHERE user_id = $1",
                        user_id,
                    )

                    # Social relations
                    await conn.execute(
                        "DELETE FROM friendships WHERE requester_id = $1 OR addressee_id = $1",
                        user_id,
                    )
                    await conn.execute(
                        "DELETE FROM follows WHERE follower_id = $1 OR following_id = $1",
                        user_id,
                    )
                    await conn.execute(
                        "DELETE FROM blocks WHERE blocker_id = $1 OR blocked_id = $1",
                        user_id,
                    )

                    # User preferences
                    await conn.execute(
                        "DELETE FROM user_preferences WHERE user_id = $1",
                        user_id,
                    )

                    # SIG memberships
                    await conn.execute(
                        "DELETE FROM sig_members WHERE user_id = $1",
                        user_id,
                    )

                    # Soft-delete comments (before posts, since comments reference posts)
                    await conn.execute(
                        "UPDATE comments SET is_deleted = true, updated_at = NOW() "
                        "WHERE user_id = $1 AND is_deleted = false",
                        user_id,
                    )

                    # Album memberships
                    await conn.execute(
                        "DELETE FROM album_members WHERE user_id = $1",
                        user_id,
                    )

                    # Soft-delete album comments
                    await conn.execute(
                        "UPDATE album_comments SET is_deleted = true, updated_at = NOW() "
                        "WHERE user_id = $1 AND is_deleted = false",
                        user_id,
                    )

                    # Disassociate album photos
                    await conn.execute(
                        "UPDATE album_photos SET uploaded_by = NULL WHERE uploaded_by = $1",
                        user_id,
                    )

                    # Soft-delete posts
                    await conn.execute(
                        "UPDATE posts SET is_deleted = true, updated_at = NOW() "
                        "WHERE user_id = $1 AND is_deleted = false",
                        user_id,
                    )
            except Exception:
                logger.warning(
                    "Failed to clean up related data during anonymization",
                    extra={"user_id": str(user_id)},
                    exc_info=True,
                )

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
    """Change role for multiple users in a single transaction.

    Raises ValueError if the operation would remove the last SUPER_ADMIN.
    """
    from app.core.database import get_pool

    # Prevent orphaning the system by demoting all SUPER_ADMINs
    if role != "SUPER_ADMIN" and user_ids:
        remaining = await user_repo.count_super_admins_excluding(user_ids)
        if remaining == 0:
            raise ValueError("Cannot demote: this would remove the last Super Admin in the system.")

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            count = await user_repo.bulk_update_role(user_ids, role, conn)
    return count
