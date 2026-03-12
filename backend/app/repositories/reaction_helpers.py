import json
import uuid as _uuid
from typing import Any


async def toggle_reaction_jsonb(
    conn: Any,
    table: str,
    row_id: str,
    user_id: str,
    reaction_type: str,
) -> dict[str, Any]:
    """Toggle a user's reaction on a row. Returns the updated reactions dict.

    Must be called within a transaction with the row already locked (FOR UPDATE).
    Explicitly converts row_id to uuid.UUID to avoid relying on PostgreSQL
    implicit casting from text to UUID.
    """
    row_uuid = row_id if isinstance(row_id, _uuid.UUID) else _uuid.UUID(row_id)
    row = await conn.fetchrow(
        f"SELECT reactions FROM {table} WHERE id = $1 FOR UPDATE",
        row_uuid,
    )
    if row is None:
        raise ValueError(f"Row {row_id} not found in {table}")

    raw = row["reactions"]
    reactions: dict[str, Any]
    if isinstance(raw, str):
        reactions = json.loads(raw)
    elif raw:
        reactions = dict(raw)
    else:
        reactions = {}

    if reaction_type not in reactions:
        reactions[reaction_type] = []

    user_list: list[str] = reactions[reaction_type]
    if user_id in user_list:
        user_list.remove(user_id)
    else:
        user_list.append(user_id)

    if not user_list:
        del reactions[reaction_type]

    await conn.execute(
        f"UPDATE {table} SET reactions = $1::jsonb, updated_at = NOW() WHERE id = $2",
        json.dumps(reactions),
        row_uuid,
    )

    # Keep like_count column in sync for posts (used by "popular" sort)
    if table == "posts":
        like_count = len(reactions.get("like", []))
        await conn.execute(
            "UPDATE posts SET like_count = $1 WHERE id = $2",
            like_count,
            row_uuid,
        )

    return reactions
