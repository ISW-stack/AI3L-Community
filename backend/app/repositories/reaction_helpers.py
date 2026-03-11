import json
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
    """
    row = await conn.fetchrow(
        f"SELECT reactions FROM {table} WHERE id = $1 FOR UPDATE",
        row_id,
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
        row_id,
    )
    return reactions
