import json
import uuid
from datetime import datetime
from typing import Any

from app.core.database import get_pool


async def insert(
    form_id: uuid.UUID,
    sig_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str,
    description: str | None,
    banner_url: str | None,
    deadline: datetime | None,
    max_respondents: int | None,
    questions: list[dict],
    allow_non_members: bool = False,
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO forms (id, sig_id, created_by, title, description, banner_url,
                               deadline, max_respondents, questions, allow_non_members)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10)
            RETURNING *
            """,
            form_id,
            sig_id,
            user_id,
            title,
            description,
            banner_url,
            deadline,
            max_respondents,
            json.dumps(questions),
            allow_non_members,
        )
        creator = await conn.fetchrow("SELECT display_name FROM users WHERE id = $1", user_id)
        result = dict(row)
        result["creator_display_name"] = creator["display_name"] if creator else "Unknown"
        return result


async def find_by_id(form_id: uuid.UUID) -> tuple[dict | None, int]:
    """Returns (row_dict, response_count) or (None, 0)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT f.*, u.display_name AS creator_display_name,
                   COALESCE(rc.cnt, 0) AS response_count
            FROM forms f
            JOIN users u ON u.id = f.created_by
            LEFT JOIN (
                SELECT form_id, COUNT(*) AS cnt FROM form_responses GROUP BY form_id
            ) rc ON rc.form_id = f.id
            WHERE f.id = $1 AND f.is_deleted = false
            """,
            form_id,
        )
        if not row:
            return None, 0
        result = dict(row)
        response_count = result.pop("response_count")
        return result, response_count


async def find_for_update(form_id: uuid.UUID, conn: Any) -> dict | None:
    row = await conn.fetchrow(
        "SELECT * FROM forms WHERE id = $1 AND is_deleted = false FOR UPDATE",
        form_id,
    )
    return dict(row) if row else None


async def update(
    form_id: uuid.UUID, fields: list[str], values: list[Any], conn: Any
) -> tuple[dict, int] | None:
    """Dynamic update within a connection. fields/values built by service."""
    _ALLOWED_FORM_FIELDS = {
        "title", "description", "banner_url", "deadline",
        "max_respondents", "questions", "allow_non_members",
        "status", "is_deleted", "updated_at",
    }
    for f in fields:
        col_name = f.split("=")[0].strip().split()[0]
        if col_name not in _ALLOWED_FORM_FIELDS:
            raise ValueError(f"Disallowed field in form update: {col_name}")
    fields.append("updated_at = NOW()")
    idx = len(values) + 1
    values.append(form_id)
    query = f"""
        UPDATE forms SET {', '.join(fields)}
        WHERE id = ${idx} AND is_deleted = false
        RETURNING *
    """
    row = await conn.fetchrow(query, *values)
    if not row:
        return None
    creator = await conn.fetchrow("SELECT display_name FROM users WHERE id = $1", row["created_by"])
    result = dict(row)
    if isinstance(result.get("questions"), str):
        result["questions"] = json.loads(result["questions"])
    result["creator_display_name"] = creator["display_name"] if creator else "Unknown"
    response_count = await conn.fetchval(
        "SELECT COUNT(*) FROM form_responses WHERE form_id = $1", form_id
    )
    return result, response_count


async def count_active(sig_id: uuid.UUID) -> int:
    pool = get_pool()
    async with pool.acquire() as conn:
        return int(
            await conn.fetchval(
                "SELECT COUNT(*) FROM forms WHERE sig_id = $1 AND is_deleted = false",
                sig_id,
            )
        )


async def find_by_sig(
    sig_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[tuple[dict, int]], int]:
    """Returns list of (row, response_count) and total."""
    pool = get_pool()
    offset = (page - 1) * page_size
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM forms WHERE sig_id = $1 AND is_deleted = false",
            sig_id,
        )
        rows = await conn.fetch(
            """
            SELECT f.*, u.display_name AS creator_display_name,
                   COALESCE(rc.cnt, 0) AS response_count
            FROM forms f
            JOIN users u ON u.id = f.created_by
            LEFT JOIN (
                SELECT form_id, COUNT(*) AS cnt FROM form_responses GROUP BY form_id
            ) rc ON rc.form_id = f.id
            WHERE f.sig_id = $1 AND f.is_deleted = false
            ORDER BY f.created_at DESC
            LIMIT $2 OFFSET $3
            """,
            sig_id,
            page_size,
            offset,
        )
        results = []
        for row in rows:
            d = dict(row)
            response_count = d.pop("response_count")
            results.append((d, response_count))
        return results, total


async def find_responses(
    form_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    """Returns (list of response dicts with user info, total count)."""
    pool = get_pool()
    offset = (page - 1) * page_size
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM form_responses WHERE form_id = $1",
            form_id,
        )
        rows = await conn.fetch(
            """
            SELECT fr.id, fr.form_id, fr.user_id, fr.answers, fr.created_at,
                   u.display_name, u.username
            FROM form_responses fr
            JOIN users u ON fr.user_id = u.id
            WHERE fr.form_id = $1
            ORDER BY fr.created_at DESC
            LIMIT $2 OFFSET $3
            """,
            form_id,
            page_size,
            offset,
        )
        results = []
        for r in rows:
            d = dict(r)
            if isinstance(d.get("answers"), str):
                d["answers"] = json.loads(d["answers"])
            results.append(d)
        return results, total


async def insert_response(
    response_id: uuid.UUID,
    form_id: uuid.UUID,
    user_id: uuid.UUID,
    answers: dict[str, Any],
    conn: Any,
) -> None:
    await conn.execute(
        """
        INSERT INTO form_responses (id, form_id, user_id, answers)
        VALUES ($1, $2, $3, $4::jsonb)
        """,
        response_id,
        form_id,
        user_id,
        json.dumps(answers),
    )


async def count_responses(form_id: uuid.UUID, conn: Any) -> int:
    return int(
        await conn.fetchval("SELECT COUNT(*) FROM form_responses WHERE form_id = $1", form_id)
    )


async def check_duplicate_response(form_id: uuid.UUID, user_id: uuid.UUID, conn: Any) -> bool:
    existing = await conn.fetchval(
        "SELECT id FROM form_responses WHERE form_id = $1 AND user_id = $2",
        form_id,
        user_id,
    )
    return existing is not None


async def lock_schema(form_id: uuid.UUID, conn: Any) -> None:
    await conn.execute(
        "UPDATE forms SET is_schema_locked = true, updated_at = NOW() WHERE id = $1",
        form_id,
    )


async def soft_delete(form_id: uuid.UUID) -> tuple[bool, str | None]:
    """Returns (deleted, created_by_str)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        form = await conn.fetchrow(
            "SELECT created_by FROM forms WHERE id = $1 AND is_deleted = false",
            form_id,
        )
        if not form:
            return False, None
        await conn.execute(
            "UPDATE forms SET is_deleted = true, updated_at = NOW() WHERE id = $1",
            form_id,
        )
        return True, str(form["created_by"])
