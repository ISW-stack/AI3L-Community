import uuid

from app.core.database import get_pool


async def insert_consent(consent_id: uuid.UUID, user_id: uuid.UUID, ip_address: str) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO privacy_consents (id, user_id, ip_address)
            VALUES ($1, $2, $3)
            """,
            consent_id,
            user_id,
            ip_address,
        )


async def has_consent(user_id: uuid.UUID) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM privacy_consents WHERE user_id = $1",
            user_id,
        )
        return count > 0
