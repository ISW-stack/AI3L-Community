"""Service layer for post citations management."""

import re
import uuid
from html.parser import HTMLParser

from loguru import logger

from app.core.blacklist import get_blocked_user_ids
from app.core.database import get_pool
from app.core.event_bus import emit
from app.core.redis import get_redis
from app.repositories import citation_repo


class CitationParser(HTMLParser):
    """Parse citation links from HTML content."""

    def __init__(self) -> None:
        super().__init__()
        self.cited_ids: list[uuid.UUID] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            attrs_dict = dict(attrs)
            if attrs_dict.get("data-citation") == "true":
                href = attrs_dict.get("href", "")
                # Extract UUID from /forum/{id} or /posts/{id} patterns
                match = re.search(
                    r"/(?:forum|posts)/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}"
                    r"-[0-9a-f]{4}-[0-9a-f]{12})",
                    href or "",
                    re.IGNORECASE,
                )
                if match:
                    try:
                        self.cited_ids.append(uuid.UUID(match.group(1)))
                    except ValueError:
                        pass


def parse_cited_post_ids(html: str) -> list[uuid.UUID]:
    """Extract cited post IDs from HTML content using safe HTML parser."""
    parser = CitationParser()
    try:
        parser.feed(html)
    except Exception:
        logger.warning("Failed to parse citations from HTML content")
        return []
    # Deduplicate while preserving order
    seen: set[uuid.UUID] = set()
    result: list[uuid.UUID] = []
    for cid in parser.cited_ids:
        if cid not in seen:
            seen.add(cid)
            result.append(cid)
    return result


async def sync_post_citations(
    post_id: uuid.UUID,
    content: str,
    author_id: str,
) -> None:
    """Sync citations: parse content, diff against existing, update."""
    new_cited_ids = parse_cited_post_ids(content)
    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Get existing citations
            existing = await citation_repo.find_existing_citations(conn, post_id)
            existing_map = {row["cited_post_id"]: row["id"] for row in existing}

            # Calculate diff
            new_ids_set = set(new_cited_ids)
            existing_ids_set = set(existing_map.keys())

            to_add = new_ids_set - existing_ids_set
            to_remove = existing_ids_set - new_ids_set

            # Delete removed citations
            if to_remove:
                remove_ids = [existing_map[cid] for cid in to_remove]
                await citation_repo.delete_citations(conn, remove_ids)

            # Insert new citations
            author_uuid = uuid.UUID(author_id)
            new_citations: list[dict] = []
            for cited_id in to_add:
                # Verify cited post exists and get author in single query
                cited_row = await conn.fetchrow(
                    "SELECT user_id FROM posts WHERE id = $1 AND is_deleted = false",
                    cited_id,
                )
                if not cited_row:
                    continue

                is_self = cited_row["user_id"] == author_uuid

                citation_id = uuid.uuid4()
                row = await citation_repo.insert_citation(
                    conn, citation_id, post_id, cited_id, is_self
                )
                new_citations.append(row)

            # Recalculate citation counts for all affected posts
            affected_posts = set()
            affected_posts.update(to_add)
            affected_posts.update(to_remove)
            for affected_id in affected_posts:
                await citation_repo.update_citation_count(conn, affected_id)

    # U6: Emit events for new non-self citations — fetch shared data once
    non_self_citations = [c for c in new_citations if not c.get("is_self_citation")]
    if non_self_citations:
        citing_post_title = "Untitled"
        citer_name = "Someone"
        try:
            pool2 = get_pool()
            async with pool2.acquire() as conn2:
                citing_post = await conn2.fetchrow(
                    "SELECT title FROM posts WHERE id = $1", post_id
                )
                citer = await conn2.fetchrow(
                    "SELECT display_name FROM users WHERE id = $1", author_uuid
                )
            if citing_post:
                citing_post_title = citing_post["title"]
            if citer:
                citer_name = citer["display_name"]
        except Exception as e:
            logger.warning(
                "Failed to fetch citation event data",
                extra={"error": str(e), "post_id": str(post_id)},
            )

        for citation in non_self_citations:
            try:
                await emit(
                    "post.cited",
                    cited_post_id=str(citation["cited_post_id"]),
                    citing_post_id=str(post_id),
                    citer_id=author_id,
                    citer_name=citer_name,
                    citing_post_title=citing_post_title,
                )
            except Exception as e:
                logger.warning(
                    "Failed to emit post.cited event",
                    extra={"error": str(e), "post_id": str(post_id)},
                )


async def get_citations_of(
    post_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    """Get posts that cite this post ('Cited by' list)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows, total = await citation_repo.find_citations_of_post(conn, post_id, page, page_size)
    result = []
    for row in rows:
        result.append(
            {
                "id": str(row["id"]),
                "post_id": str(row["post_id"]),
                "post_title": row.get("post_title", ""),
                "author_name": row.get("author_name", ""),
                "is_self_citation": row.get("is_self_citation", False),
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            }
        )
    return result, total


async def get_citing(
    post_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    """Get posts this post cites ('References' list)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows, total = await citation_repo.find_citations_by_post(conn, post_id, page, page_size)
    result = []
    for row in rows:
        result.append(
            {
                "id": str(row["id"]),
                "post_id": str(row["post_id"]),
                "post_title": row.get("post_title", ""),
                "author_name": row.get("author_name", ""),
                "is_self_citation": row.get("is_self_citation", False),
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            }
        )
    return result, total


def _escape_ilike(s: str) -> str:
    """Escape ILIKE special characters."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def search_posts_for_citation(query: str, user_id: str, limit: int = 10) -> list[dict]:
    """Search posts for citation insertion (minimal results).

    Uses FTS first, falls back to ILIKE title search for non-English content (U4).
    """
    # H6: Get blocked user IDs to exclude from search results
    blocked_ids: set[str] = set()
    try:
        redis = get_redis()
        blocked_ids = await get_blocked_user_ids(redis, user_id)
    except Exception:
        pass  # Redis failure → no filtering

    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await _citation_fts_search(conn, query, limit, blocked_ids)
        # U4: Fall back to ILIKE title search for non-English queries
        if not rows:
            rows = await _citation_ilike_search(conn, query, limit, blocked_ids)
    return [
        {
            "id": str(r["id"]),
            "title": r["title"],
            "author_name": r["author_name"],
        }
        for r in rows
    ]


async def _citation_fts_search(
    conn: object, query: str, limit: int, blocked_ids: set[str]
) -> list:
    if blocked_ids:
        blocked_uuids = [uuid.UUID(uid) for uid in blocked_ids]
        return await conn.fetch(  # type: ignore[union-attr]
            """
            SELECT p.id, p.title, u.display_name AS author_name
            FROM posts p
            JOIN users u ON p.user_id = u.id
            WHERE p.is_deleted = false
              AND p.search_vector @@ websearch_to_tsquery('english', $1)
              AND p.user_id != ALL($3::uuid[])
            ORDER BY p.created_at DESC
            LIMIT $2
            """,
            query,
            limit,
            blocked_uuids,
        )
    return await conn.fetch(  # type: ignore[union-attr]
        """
        SELECT p.id, p.title, u.display_name AS author_name
        FROM posts p
        JOIN users u ON p.user_id = u.id
        WHERE p.is_deleted = false
          AND p.search_vector @@ websearch_to_tsquery('english', $1)
        ORDER BY p.created_at DESC
        LIMIT $2
        """,
        query,
        limit,
    )


async def _citation_ilike_search(
    conn: object, query: str, limit: int, blocked_ids: set[str]
) -> list:
    pattern = f"%{_escape_ilike(query)}%"
    if blocked_ids:
        blocked_uuids = [uuid.UUID(uid) for uid in blocked_ids]
        return await conn.fetch(  # type: ignore[union-attr]
            """
            SELECT p.id, p.title, u.display_name AS author_name
            FROM posts p
            JOIN users u ON p.user_id = u.id
            WHERE p.is_deleted = false
              AND p.title ILIKE $1 ESCAPE '\\'
              AND p.user_id != ALL($3::uuid[])
            ORDER BY p.created_at DESC
            LIMIT $2
            """,
            pattern,
            limit,
            blocked_uuids,
        )
    return await conn.fetch(  # type: ignore[union-attr]
        """
        SELECT p.id, p.title, u.display_name AS author_name
        FROM posts p
        JOIN users u ON p.user_id = u.id
        WHERE p.is_deleted = false
          AND p.title ILIKE $1 ESCAPE '\\'
        ORDER BY p.created_at DESC
        LIMIT $2
        """,
        pattern,
        limit,
    )
