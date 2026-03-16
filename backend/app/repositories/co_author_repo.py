import uuid
from datetime import datetime
from typing import Any


async def insert_co_author(
    conn: Any,
    co_author_id: uuid.UUID,
    post_id: uuid.UUID,
    user_id: uuid.UUID | None,
    display_name: str,
    affiliation: str | None,
    orcid: str | None,
    is_external: bool,
    status: str,
    invited_by: uuid.UUID,
) -> dict:
    row = await conn.fetchrow(
        """
        INSERT INTO post_co_authors (id, post_id, user_id, display_name, affiliation, orcid,
                                     is_external, status, invited_by)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING *
        """,
        co_author_id,
        post_id,
        user_id,
        display_name,
        affiliation,
        orcid,
        is_external,
        status,
        invited_by,
    )
    return dict(row)


async def find_co_authors_by_post(conn: Any, post_id: uuid.UUID) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT pca.*, u.display_name AS user_display_name, u.avatar_url AS user_avatar_url
        FROM post_co_authors pca
        LEFT JOIN users u ON pca.user_id = u.id
        WHERE pca.post_id = $1 AND pca.status = 'ACCEPTED'
        ORDER BY pca.invited_at ASC
        """,
        post_id,
    )
    return [dict(r) for r in rows]


async def find_co_authors_batch(conn: Any, post_ids: list[uuid.UUID]) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT pca.*, u.display_name AS user_display_name, u.avatar_url AS user_avatar_url
        FROM post_co_authors pca
        LEFT JOIN users u ON pca.user_id = u.id
        WHERE pca.post_id = ANY($1::uuid[]) AND pca.status = 'ACCEPTED'
        ORDER BY pca.invited_at ASC
        """,
        post_ids,
    )
    return [dict(r) for r in rows]


async def find_co_author_by_id(conn: Any, co_author_id: uuid.UUID) -> dict | None:
    row = await conn.fetchrow(
        "SELECT * FROM post_co_authors WHERE id = $1",
        co_author_id,
    )
    return dict(row) if row else None


async def is_accepted_co_author(conn: Any, post_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    row = await conn.fetchval(
        """
        SELECT 1 FROM post_co_authors
        WHERE post_id = $1 AND user_id = $2 AND status = 'ACCEPTED'
        """,
        post_id,
        user_id,
    )
    return row is not None


async def count_co_authors(conn: Any, post_id: uuid.UUID) -> int:
    count = await conn.fetchval(
        "SELECT COUNT(*) FROM post_co_authors "
        "WHERE post_id = $1 AND status IN ('PENDING', 'ACCEPTED')",
        post_id,
    )
    return count or 0


async def delete_co_author(conn: Any, co_author_id: uuid.UUID) -> bool:
    result = await conn.execute(
        "DELETE FROM post_co_authors WHERE id = $1",
        co_author_id,
    )
    return bool(result == "DELETE 1")


async def find_pending_invitations(
    conn: Any, user_id: uuid.UUID, page: int, page_size: int
) -> tuple[list[dict], int]:
    offset = (page - 1) * page_size
    rows = await conn.fetch(
        """
        SELECT pca.*, p.title AS post_title,
               inviter.display_name AS invited_by_name,
               COUNT(*) OVER() AS _total
        FROM post_co_authors pca
        JOIN posts p ON pca.post_id = p.id
        JOIN users inviter ON pca.invited_by = inviter.id
        WHERE pca.user_id = $1 AND pca.status = 'PENDING'
        ORDER BY pca.invited_at DESC
        LIMIT $2 OFFSET $3
        """,
        user_id,
        page_size,
        offset,
    )
    if rows:
        total = rows[0]["_total"]
        result = [{k: v for k, v in dict(r).items() if k != "_total"} for r in rows]
    else:
        total = 0
        result = []
    return result, total


async def update_status(
    conn: Any, co_author_id: uuid.UUID, status: str, responded_at: datetime
) -> bool:
    result = await conn.execute(
        "UPDATE post_co_authors SET status = $1, responded_at = $2 WHERE id = $3",
        status,
        responded_at,
        co_author_id,
    )
    return bool(result == "UPDATE 1")


async def find_co_authored_posts(
    conn: Any, user_id: uuid.UUID, page: int, page_size: int
) -> tuple[list[dict], int]:
    offset = (page - 1) * page_size
    rows = await conn.fetch(
        """
        SELECT p.id, p.title, p.created_at,
               COUNT(*) OVER() AS _total
        FROM post_co_authors pca
        JOIN posts p ON pca.post_id = p.id
        WHERE pca.user_id = $1 AND pca.status = 'ACCEPTED' AND p.is_deleted = false
        ORDER BY p.created_at DESC
        LIMIT $2 OFFSET $3
        """,
        user_id,
        page_size,
        offset,
    )
    if rows:
        total = rows[0]["_total"]
        result = [{k: v for k, v in dict(r).items() if k != "_total"} for r in rows]
    else:
        total = 0
        result = []
    return result, total


async def find_existing_by_user(conn: Any, post_id: uuid.UUID, user_id: uuid.UUID) -> dict | None:
    """Check if a user already has a co-author entry (any status) for a post."""
    row = await conn.fetchrow(
        "SELECT * FROM post_co_authors WHERE post_id = $1 AND user_id = $2",
        post_id,
        user_id,
    )
    return dict(row) if row else None


async def delete_by_user_id(conn: Any, user_id: uuid.UUID) -> int:
    """Delete all co-author entries for a user (GDPR cleanup)."""
    result = await conn.execute(
        "DELETE FROM post_co_authors WHERE user_id = $1",
        user_id,
    )
    return int(result.split()[-1])
