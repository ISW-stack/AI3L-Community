"""Repository for friend recommendations."""

import uuid
from typing import Any

import asyncpg


async def find_recommendations(
    conn: asyncpg.Connection, user_id: uuid.UUID, limit: int = 10
) -> list[Any]:
    """Get precomputed recommendations for a user, excluding dismissed."""
    return list(
        await conn.fetch(
            """
        SELECT fr.*, u.display_name, u.username, u.avatar_url, u.affiliation
        FROM friend_recommendations fr
        JOIN users u ON fr.recommended_user_id = u.id
        WHERE fr.user_id = $1
          AND fr.recommended_user_id NOT IN (
              SELECT dismissed_user_id FROM dismissed_recommendations WHERE user_id = $1
          )
          AND u.is_deleted = false AND u.is_banned = false
        ORDER BY fr.score DESC
        LIMIT $2
        """,
            user_id,
            limit,
        )
    )


async def dismiss_recommendation(
    conn: asyncpg.Connection, user_id: uuid.UUID, dismissed_user_id: uuid.UUID
) -> None:
    """Mark a recommendation as dismissed."""
    await conn.execute(
        """
        INSERT INTO dismissed_recommendations (id, user_id, dismissed_user_id)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id, dismissed_user_id) DO NOTHING
        """,
        uuid.uuid4(),
        user_id,
        dismissed_user_id,
    )


async def delete_all_recommendations(conn: asyncpg.Connection) -> None:
    """Delete all recommendations (before refresh)."""
    await conn.execute("DELETE FROM friend_recommendations")


async def insert_recommendations_batch(
    conn: asyncpg.Connection, rows: list[dict[str, Any]]
) -> None:
    """Batch insert recommendations using executemany."""
    if not rows:
        return
    await conn.executemany(
        """
        INSERT INTO friend_recommendations (id, user_id, recommended_user_id, score, reasons)
        VALUES ($1, $2, $3, $4, $5::jsonb)
        """,
        [(r["id"], r["user_id"], r["recommended_user_id"], r["score"], r["reasons"]) for r in rows],
    )


async def count_active_users(conn: asyncpg.Connection) -> int:
    """Count non-deleted, non-banned, non-guest users."""
    row = await conn.fetchrow(
        "SELECT COUNT(*) AS cnt FROM users "
        "WHERE is_deleted = false AND is_banned = false AND role != 'GUEST'"
    )
    return row["cnt"] if row else 0
