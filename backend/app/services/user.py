import uuid

from loguru import logger

from app.core.event_bus import emit
from app.core.redis import get_redis
from app.core.security import hash_password, validate_password_policy, verify_password
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
    pw_hash = hash_password(password)
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
) -> dict | None:
    return await user_repo.update_profile(
        user_id,
        display_name=display_name,
        bio=bio,
        affiliation=affiliation,
        orcid=orcid,
        avatar_url=avatar_url,
    )


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

    # Revoke all Redis sessions for this user (batch delete in one round-trip)
    redis = get_redis()
    session_keys = [f"session:{r.value}:{user_id}" for r in UserRole]
    await redis.delete(*session_keys)

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

    if not verify_password(old_password, pw_hash):
        raise ValueError("Current password is incorrect.")

    error = validate_password_policy(new_password)
    if error:
        raise ValueError(error)

    new_hash = hash_password(new_password)
    await user_repo.update_password_hash(user_id, new_hash)
    logger.info("Password changed", extra={"user_id": str(user_id)})
    return True


async def list_users(offset: int = 0, limit: int = 50) -> tuple[list[dict], int]:
    return await user_repo.list_all(offset, limit)
