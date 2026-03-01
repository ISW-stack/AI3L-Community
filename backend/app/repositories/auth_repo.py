import uuid
from datetime import datetime

from app.core.database import get_pool


async def find_invite_code(code: str) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM invite_codes WHERE code = $1 AND expires_at > NOW() AND consumed_at IS NULL",
            code,
        )
        return dict(row) if row else None


async def consume_invite_code(code: str, user_id: uuid.UUID) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE invite_codes SET consumed_at = NOW(), consumed_by = $1 WHERE code = $2",
            user_id,
            code,
        )


async def insert_invite_code(
    code_id: uuid.UUID, code: str, creator_id: uuid.UUID, expires_at: datetime
) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO invite_codes (id, code, created_by, expires_at) VALUES ($1, $2, $3, $4)",
            code_id,
            code,
            creator_id,
            expires_at,
        )
