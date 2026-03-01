import uuid

from loguru import logger

from app.core.redis import get_redis
from app.repositories import privacy_repo


async def create_consent(user_id: str, ip_address: str) -> None:
    """Record privacy consent for a registered user."""
    consent_id = uuid.uuid4()
    await privacy_repo.insert_consent(consent_id, uuid.UUID(user_id), ip_address)
    logger.info("Privacy consent recorded", extra={"user_id": user_id})


async def has_consent(user_id: str) -> bool:
    """Check if a registered user has already given consent."""
    return await privacy_repo.has_consent(uuid.UUID(user_id))


async def create_guest_consent(guest_id: str) -> None:
    """Record consent for a guest in Redis (45-minute TTL)."""
    redis = get_redis()
    await redis.set(f"consent:guest:{guest_id}", "1", ex=2700)  # 45 min


async def has_guest_consent(guest_id: str) -> bool:
    """Check if a guest has given consent in this session."""
    redis = get_redis()
    return bool(await redis.exists(f"consent:guest:{guest_id}"))
