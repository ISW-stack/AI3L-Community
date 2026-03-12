import uuid

from app.core.database import get_pool


async def get_preferences(user_id: uuid.UUID) -> dict | None:
    """Fetch user preferences row. Returns None if no row exists."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT theme, notify_mentions, notify_replies, notify_sig_posts "
            "FROM user_preferences WHERE user_id = $1",
            user_id,
        )
        return dict(row) if row else None


async def upsert_preferences(user_id: uuid.UUID, data: dict) -> dict:
    """Insert or update user preferences. Returns the resulting row."""
    pool = get_pool()

    # Build SET clause from provided fields
    allowed = {"theme", "notify_mentions", "notify_replies", "notify_sig_posts"}
    fields = {k: v for k, v in data.items() if k in allowed and v is not None}

    if not fields:
        # Nothing to update; return existing or defaults
        existing = await get_preferences(user_id)
        if existing:
            return existing
        return {
            "theme": "light",
            "notify_mentions": True,
            "notify_replies": True,
            "notify_sig_posts": True,
        }

    columns = list(fields.keys())
    values = list(fields.values())

    # Build INSERT columns/values
    insert_cols = ["user_id"] + columns
    insert_placeholders = ", ".join(f"${i}" for i in range(1, len(insert_cols) + 1))

    # Build ON CONFLICT SET clause
    set_parts = [f"{col} = EXCLUDED.{col}" for col in columns]
    set_parts.append("updated_at = NOW()")
    set_clause = ", ".join(set_parts)

    sql = (
        f"INSERT INTO user_preferences ({', '.join(insert_cols)}) "
        f"VALUES ({insert_placeholders}) "
        f"ON CONFLICT (user_id) DO UPDATE SET {set_clause} "
        "RETURNING theme, notify_mentions, notify_replies, notify_sig_posts"
    )

    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, user_id, *values)
        return dict(row)
