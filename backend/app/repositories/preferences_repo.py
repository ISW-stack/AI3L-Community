import re
import uuid

from app.core.database import get_pool

_ALLOWED_PREFERENCE_COLUMNS = frozenset(
    {"theme", "notify_mentions", "notify_replies", "notify_sig_posts", "dm_friends_only"}
)
_SAFE_COLUMN_RE = re.compile(r"^[a-z_]+$")


async def get_preferences(user_id: uuid.UUID) -> dict | None:
    """Fetch user preferences row. Returns None if no row exists."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT theme, notify_mentions, notify_replies, notify_sig_posts, dm_friends_only "
            "FROM user_preferences WHERE user_id = $1",
            user_id,
        )
        return dict(row) if row else None


async def upsert_preferences(user_id: uuid.UUID, data: dict) -> dict:
    """Insert or update user preferences. Returns the resulting row."""
    # Reject any unknown columns up-front (defense-in-depth) — before touching DB
    unknown = set(data.keys()) - _ALLOWED_PREFERENCE_COLUMNS
    if unknown:
        raise ValueError(f"Unknown preference columns: {unknown}")

    pool = get_pool()

    # Build SET clause from provided fields (regex guard as defense-in-depth)
    fields = {
        k: v
        for k, v in data.items()
        if k in _ALLOWED_PREFERENCE_COLUMNS and v is not None and _SAFE_COLUMN_RE.match(k)
    }

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
            "dm_friends_only": False,
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
        "RETURNING theme, notify_mentions, notify_replies, notify_sig_posts, dm_friends_only"
    )

    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, user_id, *values)
        return dict(row)
