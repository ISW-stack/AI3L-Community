import uuid
from typing import Any

from app.core.database import get_pool

_UNSET: Any = object()  # sentinel for "field not provided"

_EVENT_SELECT = """
    SELECT e.*,
           u.id AS author_id, u.username AS author_username,
           u.display_name AS author_display_name, u.avatar_url AS author_avatar_url,
           s.name AS sig_name
    FROM events e
    JOIN users u ON e.user_id = u.id
    LEFT JOIN sigs s ON e.sig_id = s.id
"""


async def insert(
    event_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str,
    content: str,
    sig_id: uuid.UUID | None,
    visibility: list[str],
    allow_comments: bool,
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            WITH inserted AS (
                INSERT INTO events (id, user_id, title, content, sig_id, visibility, allow_comments)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING *
            )
            {_EVENT_SELECT.replace("FROM events e", "FROM inserted e")}
            """,
            event_id,
            user_id,
            title,
            content,
            sig_id,
            visibility,
            allow_comments,
        )
        return dict(row)


async def find_by_id(event_id: uuid.UUID, user_role: str | None = None) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        where = " WHERE e.id = $1 AND e.is_deleted = false"
        params: list[Any] = [event_id]
        if user_role and user_role != "SUPER_ADMIN":
            where += " AND e.visibility @> ARRAY[$2]::TEXT[]"
            params.append(user_role)
        row = await conn.fetchrow(f"{_EVENT_SELECT}{where}", *params)
        return dict(row) if row else None


async def find_for_update(event_id: uuid.UUID) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM events WHERE id = $1 AND is_deleted = false FOR UPDATE",
            event_id,
        )
        return dict(row) if row else None


async def find_many(
    page: int = 1,
    page_size: int = 20,
    sig_id: uuid.UUID | None = None,
    user_role: str | None = None,
) -> dict:
    _select_count = _EVENT_SELECT.replace(
        "FROM events e", ", COUNT(*) OVER() AS _total\n    FROM events e", 1
    )
    pool = get_pool()

    where = " WHERE e.is_deleted = false"
    params: list[Any] = []
    idx = 1

    if user_role and user_role != "SUPER_ADMIN":
        where += f" AND e.visibility @> ARRAY[${idx}]::TEXT[]"
        params.append(user_role)
        idx += 1

    if sig_id:
        where += f" AND e.sig_id = ${idx}"
        params.append(sig_id)
        idx += 1

    offset = (page - 1) * page_size
    params.extend([page_size, offset])

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"{_select_count}{where} ORDER BY e.created_at DESC LIMIT ${idx} OFFSET ${idx + 1}",
            *params,
        )
        if rows:
            total = rows[0]["_total"]
            result = [{k: v for k, v in dict(r).items() if k != "_total"} for r in rows]
        else:
            # Build count query with same filters
            count_where = " WHERE is_deleted = false"
            count_params: list[Any] = []
            count_idx = 1
            if user_role and user_role != "SUPER_ADMIN":
                count_where += f" AND visibility @> ARRAY[${count_idx}]::TEXT[]"
                count_params.append(user_role)
                count_idx += 1
            if sig_id:
                count_where += f" AND sig_id = ${count_idx}"
                count_params.append(sig_id)
            total = await conn.fetchval(
                f"SELECT COUNT(*) FROM events{count_where}",
                *count_params,
            )
            result = []
        return {"events": result, "total": total}


async def update(
    event_id: uuid.UUID,
    title: str | None,
    content: str | None,
    sig_id: Any = _UNSET,
    visibility: list[str] | None = None,
    allow_comments: bool | None = None,
    version: int = 1,
) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            current = await conn.fetchrow(
                "SELECT * FROM events WHERE id = $1 AND is_deleted = false FOR UPDATE",
                event_id,
            )
            if not current:
                return None
            if current["version"] != version:
                raise ValueError("Version conflict. The event was modified by someone else.")

            new_title = title if title is not None else current["title"]
            new_content = content if content is not None else current["content"]
            new_sig_id = current["sig_id"] if sig_id is _UNSET else sig_id
            new_visibility = visibility if visibility is not None else current["visibility"]
            new_allow_comments = allow_comments if allow_comments is not None else current["allow_comments"]

            row = await conn.fetchrow(
                f"""
                WITH updated AS (
                    UPDATE events
                    SET title = $2, content = $3, sig_id = $4, visibility = $5,
                        allow_comments = $6, version = version + 1, updated_at = NOW()
                    WHERE id = $1
                    RETURNING *
                )
                {_EVENT_SELECT.replace("FROM events e", "FROM updated e")}
                """,
                event_id,
                new_title,
                new_content,
                new_sig_id,
                new_visibility,
                new_allow_comments,
            )
            return dict(row) if row else None


async def soft_delete(event_id: uuid.UUID) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE events SET is_deleted = true, updated_at = NOW() "
            "WHERE id = $1 AND is_deleted = false",
            event_id,
        )
        return result == "UPDATE 1"


async def update_reactions(event_id: uuid.UUID, user_id: str, reaction: str) -> dict | None:
    """Toggle a reaction on an event. Returns updated event row."""
    from app.repositories.reaction_helpers import toggle_reaction_jsonb

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            check = await conn.fetchrow(
                "SELECT id FROM events WHERE id = $1 AND is_deleted = false",
                event_id,
            )
            if not check:
                return None

            await toggle_reaction_jsonb(conn, "events", str(event_id), user_id, reaction)

            result = await conn.fetchrow(
                f"{_EVENT_SELECT} WHERE e.id = $1",
                event_id,
            )
            return dict(result) if result else None


async def find_event_for_comment(event_id: uuid.UUID, conn: Any) -> dict | None:
    """Check event exists and get comment-relevant fields (within existing connection)."""
    row = await conn.fetchrow(
        "SELECT id, user_id, allow_comments, comment_count "
        "FROM events WHERE id = $1 AND is_deleted = false FOR UPDATE",
        event_id,
    )
    return dict(row) if row else None
