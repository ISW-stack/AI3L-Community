import uuid
from typing import Any


async def find_citations_of_post(
    conn: Any, cited_post_id: uuid.UUID, page: int, page_size: int
) -> tuple[list[dict], int]:
    """Posts that cite this post ('Cited by' list)."""
    offset = (page - 1) * page_size
    rows = await conn.fetch(
        """
        SELECT pc.id, pc.citing_post_id AS post_id, pc.is_self_citation, pc.created_at,
               p.title AS post_title,
               u.display_name AS author_name,
               COUNT(*) OVER() AS _total
        FROM post_citations pc
        JOIN posts p ON pc.citing_post_id = p.id
        JOIN users u ON p.user_id = u.id
        WHERE pc.cited_post_id = $1 AND p.is_deleted = false
        ORDER BY pc.created_at DESC
        LIMIT $2 OFFSET $3
        """,
        cited_post_id,
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


async def find_citations_by_post(
    conn: Any, citing_post_id: uuid.UUID, page: int, page_size: int
) -> tuple[list[dict], int]:
    """Posts this post cites ('References' list)."""
    offset = (page - 1) * page_size
    rows = await conn.fetch(
        """
        SELECT pc.id, pc.cited_post_id AS post_id, pc.is_self_citation, pc.created_at,
               p.title AS post_title,
               u.display_name AS author_name,
               COUNT(*) OVER() AS _total
        FROM post_citations pc
        JOIN posts p ON pc.cited_post_id = p.id
        JOIN users u ON p.user_id = u.id
        WHERE pc.citing_post_id = $1 AND p.is_deleted = false
        ORDER BY pc.created_at DESC
        LIMIT $2 OFFSET $3
        """,
        citing_post_id,
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


async def find_existing_citations(
    conn: Any, citing_post_id: uuid.UUID, limit: int = 5000
) -> list[dict]:
    """Current citations for a citing post (for diff). Capped to prevent OOM."""
    rows = await conn.fetch(
        "SELECT id, cited_post_id FROM post_citations WHERE citing_post_id = $1 LIMIT $2",
        citing_post_id,
        limit,
    )
    return [dict(r) for r in rows]


async def insert_citation(
    conn: Any,
    citation_id: uuid.UUID,
    citing_post_id: uuid.UUID,
    cited_post_id: uuid.UUID,
    is_self_citation: bool,
) -> dict:
    row = await conn.fetchrow(
        """
        INSERT INTO post_citations (id, citing_post_id, cited_post_id, is_self_citation)
        VALUES ($1, $2, $3, $4)
        RETURNING *
        """,
        citation_id,
        citing_post_id,
        cited_post_id,
        is_self_citation,
    )
    return dict(row)


async def delete_citations(conn: Any, citation_ids: list[uuid.UUID]) -> int:
    if not citation_ids:
        return 0
    result = await conn.execute(
        "DELETE FROM post_citations WHERE id = ANY($1::uuid[])",
        citation_ids,
    )
    return int(result.split()[-1])


async def update_citation_count(conn: Any, post_id: uuid.UUID) -> int:
    """Recalculate citation_count from post_citations table."""
    count: int = await conn.fetchval(
        """
        SELECT COUNT(*) FROM post_citations pc
        JOIN posts p ON pc.citing_post_id = p.id
        WHERE pc.cited_post_id = $1 AND p.is_deleted = false
        """,
        post_id,
    )
    await conn.execute(
        "UPDATE posts SET citation_count = $1 WHERE id = $2",
        count,
        post_id,
    )
    return count
