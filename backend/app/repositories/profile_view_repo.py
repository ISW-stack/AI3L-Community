import uuid
from typing import Any

from app.core.database import get_pool


async def upsert_view(conn: Any, profile_id: uuid.UUID, viewer_id: uuid.UUID) -> bool:
    """Insert or update a profile view. Returns True if this is a new viewer."""
    row = await conn.fetchrow(
        """
        INSERT INTO profile_views (id, profile_id, viewer_id, view_count, last_viewed_at)
        VALUES ($1, $2, $3, 1, NOW())
        ON CONFLICT (profile_id, viewer_id) DO UPDATE
            SET view_count = profile_views.view_count + 1,
                last_viewed_at = NOW()
        RETURNING (xmax = 0) AS is_new
        """,
        uuid.uuid4(),
        profile_id,
        viewer_id,
    )
    return bool(row["is_new"]) if row else False


async def increment_total_counter(conn: Any, profile_id: uuid.UUID) -> None:
    """Increment the total profile view counter on the users table."""
    await conn.execute(
        """
        UPDATE users SET profile_view_count_total = COALESCE(profile_view_count_total, 0) + 1
        WHERE id = $1
        """,
        profile_id,
    )


async def increment_unique_counter(conn: Any, profile_id: uuid.UUID) -> None:
    """Increment the unique profile view counter on the users table."""
    await conn.execute(
        """
        UPDATE users SET profile_view_count_unique = COALESCE(profile_view_count_unique, 0) + 1
        WHERE id = $1
        """,
        profile_id,
    )


async def get_view_counts(conn: Any, profile_id: uuid.UUID) -> tuple[int, int]:
    """Return (unique_count, total_count) for a profile."""
    row = await conn.fetchrow(
        """
        SELECT COALESCE(profile_view_count_unique, 0) AS unique_count,
               COALESCE(profile_view_count_total, 0) AS total_count
        FROM users WHERE id = $1
        """,
        profile_id,
    )
    if row:
        return row["unique_count"], row["total_count"]
    return 0, 0


async def delete_by_profile_or_viewer(conn: Any, user_id: uuid.UUID) -> int:
    """Delete all profile view records for a user (GDPR cleanup)."""
    result = await conn.execute(
        "DELETE FROM profile_views WHERE profile_id = $1 OR viewer_id = $1",
        user_id,
    )
    return int(result.split()[-1])
