import uuid

from loguru import logger

from app.core.database import get_pool
from app.core.redis import get_redis


async def create_consent(user_id: str, ip_address: str) -> None:
    """Record privacy consent for a registered user."""
    pool = get_pool()
    consent_id = uuid.uuid4()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO privacy_consents (id, user_id, ip_address)
            VALUES ($1, $2, $3)
            """,
            consent_id,
            uuid.UUID(user_id),
            ip_address,
        )
    logger.info("Privacy consent recorded", extra={"user_id": user_id})


async def has_consent(user_id: str) -> bool:
    """Check if a registered user has already given consent."""
    pool = get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM privacy_consents WHERE user_id = $1",
            uuid.UUID(user_id),
        )
        return count > 0


async def create_guest_consent(guest_id: str) -> None:
    """Record consent for a guest in Redis (45-minute TTL)."""
    redis = get_redis()
    await redis.set(f"consent:guest:{guest_id}", "1", ex=2700)  # 45 min


async def has_guest_consent(guest_id: str) -> bool:
    """Check if a guest has given consent in this session."""
    redis = get_redis()
    return bool(await redis.exists(f"consent:guest:{guest_id}"))
