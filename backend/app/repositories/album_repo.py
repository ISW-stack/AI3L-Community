"""Album repository — raw SQL queries for albums, members, photos, and comments."""

import uuid
from typing import Any

# ── Albums ──────────────────────────────────────────────────────────────────


async def insert_album(
    conn: Any,
    album_id: uuid.UUID,
    title: str,
    description: str | None,
    created_by: uuid.UUID,
) -> dict:
    row = await conn.fetchrow(
        """
        INSERT INTO albums (id, title, description, created_by)
        VALUES ($1, $2, $3, $4)
        RETURNING *
        """,
        album_id,
        title,
        description,
        created_by,
    )
    return dict(row)


async def find_album_by_id(conn: Any, album_id: uuid.UUID) -> dict | None:
    row = await conn.fetchrow(
        """
        SELECT a.*,
               u.display_name AS created_by_name,
               (SELECT COUNT(*) FROM album_photos ap
                WHERE ap.album_id = a.id) AS photo_count,
               (SELECT COUNT(*) FROM album_members am
                WHERE am.album_id = a.id AND am.status = 'ACCEPTED') AS member_count
        FROM albums a
        LEFT JOIN users u ON a.created_by = u.id
        WHERE a.id = $1 AND a.is_deleted = false
        """,
        album_id,
    )
    return dict(row) if row else None


async def find_albums(
    conn: Any,
    page: int = 1,
    page_size: int = 20,
    exclude_user_ids: list[uuid.UUID] | None = None,
) -> tuple[list[dict], int]:
    offset = (page - 1) * page_size
    exclusion_clause = ""
    params: list = [page_size, offset]
    if exclude_user_ids:
        exclusion_clause = " AND a.created_by != ALL($3::uuid[])"
        params.append(exclude_user_ids)
    rows = await conn.fetch(
        f"""
        SELECT a.*,
               u.display_name AS created_by_name,
               COUNT(*) OVER() AS _total,
               (SELECT COUNT(*) FROM album_photos ap
                WHERE ap.album_id = a.id) AS photo_count,
               (SELECT COUNT(*) FROM album_members am
                WHERE am.album_id = a.id AND am.status = 'ACCEPTED') AS member_count
        FROM albums a
        LEFT JOIN users u ON a.created_by = u.id
        WHERE a.is_deleted = false{exclusion_clause}
        ORDER BY a.created_at DESC
        LIMIT $1 OFFSET $2
        """,
        *params,
    )
    if rows:
        total = rows[0]["_total"]
        result = [{k: v for k, v in dict(r).items() if k != "_total"} for r in rows]
        return result, total
    return [], 0


async def update_album(conn: Any, album_id: uuid.UUID, **fields: Any) -> dict | None:
    _ALLOWED = {"title", "description"}
    set_parts: list[str] = []
    values: list[Any] = []
    idx = 1
    for field_name, value in fields.items():
        if field_name not in _ALLOWED:
            continue
        set_parts.append(f"{field_name} = ${idx}")
        values.append(value)
        idx += 1

    if not set_parts:
        return await find_album_by_id(conn, album_id)

    values.append(album_id)
    query = (
        f"UPDATE albums SET {', '.join(set_parts)}, updated_at = NOW() "
        f"WHERE id = ${idx} AND is_deleted = false RETURNING *"
    )
    row = await conn.fetchrow(query, *values)
    if not row:
        return None
    return await find_album_by_id(conn, album_id)


async def soft_delete_album(conn: Any, album_id: uuid.UUID) -> bool:
    result = await conn.execute(
        "UPDATE albums SET is_deleted = true, updated_at = NOW() "
        "WHERE id = $1 AND is_deleted = false",
        album_id,
    )
    return bool(result == "UPDATE 1")


async def find_all_photos_for_album(conn: Any, album_id: uuid.UUID) -> list[dict]:
    """Get all photos for an album (for cascade cleanup)."""
    rows = await conn.fetch(
        "SELECT id, storage_key, thumbnail_key, file_size_bytes, uploaded_by "
        "FROM album_photos WHERE album_id = $1",
        album_id,
    )
    return [dict(r) for r in rows]


async def delete_all_photos_for_album(conn: Any, album_id: uuid.UUID) -> int:
    """Hard-delete all photos for an album."""
    result = await conn.execute(
        "DELETE FROM album_photos WHERE album_id = $1",
        album_id,
    )
    return int(result.split()[-1])


async def delete_all_comments_for_album(conn: Any, album_id: uuid.UUID) -> int:
    """Hard-delete all comments for an album."""
    result = await conn.execute(
        "DELETE FROM album_comments WHERE album_id = $1",
        album_id,
    )
    return int(result.split()[-1])


async def delete_all_members_for_album(conn: Any, album_id: uuid.UUID) -> int:
    """Hard-delete all members for an album."""
    result = await conn.execute(
        "DELETE FROM album_members WHERE album_id = $1",
        album_id,
    )
    return int(result.split()[-1])


async def archive_album(conn: Any, album_id: uuid.UUID, archived: bool) -> bool:
    result = await conn.execute(
        "UPDATE albums SET is_archived = $1, updated_at = NOW() "
        "WHERE id = $2 AND is_deleted = false",
        archived,
        album_id,
    )
    return bool(result == "UPDATE 1")


async def set_cover_photo(conn: Any, album_id: uuid.UUID, storage_key: str | None) -> bool:
    """Set album cover_photo_url to a MinIO storage key (or None to clear)."""
    result = await conn.execute(
        "UPDATE albums SET cover_photo_url = $1, updated_at = NOW() "
        "WHERE id = $2 AND is_deleted = false",
        storage_key,
        album_id,
    )
    return bool(result == "UPDATE 1")


async def find_first_photo_key(conn: Any, album_id: uuid.UUID) -> str | None:
    """Get the storage_key of the earliest photo in an album."""
    row = await conn.fetchrow(
        "SELECT storage_key FROM album_photos "
        "WHERE album_id = $1 ORDER BY created_at ASC LIMIT 1",
        album_id,
    )
    return row["storage_key"] if row else None


# ── Members ─────────────────────────────────────────────────────────────────


async def insert_member(
    conn: Any,
    member_id: uuid.UUID,
    album_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
    status: str,
) -> dict:
    row = await conn.fetchrow(
        """
        INSERT INTO album_members (id, album_id, user_id, role, status)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
        """,
        member_id,
        album_id,
        user_id,
        role,
        status,
    )
    return dict(row)


async def find_member(conn: Any, album_id: uuid.UUID, user_id: uuid.UUID) -> dict | None:
    row = await conn.fetchrow(
        "SELECT * FROM album_members WHERE album_id = $1 AND user_id = $2",
        album_id,
        user_id,
    )
    return dict(row) if row else None


async def find_members(
    conn: Any,
    album_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    offset = (page - 1) * page_size
    rows = await conn.fetch(
        """
        SELECT am.*,
               u.display_name, u.username, u.avatar_url,
               COUNT(*) OVER() AS _total
        FROM album_members am
        JOIN users u ON am.user_id = u.id
        WHERE am.album_id = $1
        ORDER BY am.joined_at DESC
        LIMIT $2 OFFSET $3
        """,
        album_id,
        page_size,
        offset,
    )
    if rows:
        total = rows[0]["_total"]
        result = [{k: v for k, v in dict(r).items() if k != "_total"} for r in rows]
        return result, total
    return [], 0


async def update_member_status(
    conn: Any, member_id: uuid.UUID, status: str, album_id: uuid.UUID | None = None
) -> bool:
    if album_id is not None:
        result = await conn.execute(
            "UPDATE album_members SET status = $1 WHERE id = $2 AND album_id = $3",
            status,
            member_id,
            album_id,
        )
    else:
        result = await conn.execute(
            "UPDATE album_members SET status = $1 WHERE id = $2",
            status,
            member_id,
        )
    return bool(result == "UPDATE 1")


async def update_member_role(conn: Any, member_id: uuid.UUID, role: str) -> bool:
    result = await conn.execute(
        "UPDATE album_members SET role = $1 WHERE id = $2",
        role,
        member_id,
    )
    return bool(result == "UPDATE 1")


async def delete_member(conn: Any, album_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    result = await conn.execute(
        "DELETE FROM album_members WHERE album_id = $1 AND user_id = $2",
        album_id,
        user_id,
    )
    return bool(result == "DELETE 1")


async def count_members(conn: Any, album_id: uuid.UUID) -> int:
    result = await conn.fetchval(
        "SELECT COUNT(*) FROM album_members WHERE album_id = $1 AND status = 'ACCEPTED'",
        album_id,
    )
    return int(result)


# ── Photos ──────────────────────────────────────────────────────────────────


async def insert_photo(
    conn: Any,
    photo_id: uuid.UUID,
    album_id: uuid.UUID,
    uploaded_by: uuid.UUID,
    storage_key: str,
    original_filename: str,
    file_size_bytes: int,
    content_type: str,
    width: int | None = None,
    height: int | None = None,
    is_zip: bool = False,
) -> dict:
    row = await conn.fetchrow(
        """
        INSERT INTO album_photos
            (id, album_id, uploaded_by, storage_key, original_filename,
             file_size_bytes, content_type, width, height, is_zip)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING *
        """,
        photo_id,
        album_id,
        uploaded_by,
        storage_key,
        original_filename,
        file_size_bytes,
        content_type,
        width,
        height,
        is_zip,
    )
    return dict(row)


async def find_photo_by_id(conn: Any, photo_id: uuid.UUID) -> dict | None:
    row = await conn.fetchrow(
        """
        SELECT p.*, u.display_name AS uploaded_by_name
        FROM album_photos p
        LEFT JOIN users u ON p.uploaded_by = u.id
        WHERE p.id = $1
        """,
        photo_id,
    )
    return dict(row) if row else None


async def find_photos(
    conn: Any,
    album_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    exclude_user_ids: list[uuid.UUID] | None = None,
) -> tuple[list[dict], int]:
    offset = (page - 1) * page_size
    exclusion_clause = ""
    params: list = [album_id, page_size, offset]
    if exclude_user_ids:
        exclusion_clause = " AND p.uploaded_by != ALL($4::uuid[])"
        params.append(exclude_user_ids)
    rows = await conn.fetch(
        f"""
        SELECT p.*, u.display_name AS uploaded_by_name,
               COUNT(*) OVER() AS _total
        FROM album_photos p
        LEFT JOIN users u ON p.uploaded_by = u.id
        WHERE p.album_id = $1{exclusion_clause}
        ORDER BY p.created_at DESC
        LIMIT $2 OFFSET $3
        """,
        *params,
    )
    if rows:
        total = rows[0]["_total"]
        result = [{k: v for k, v in dict(r).items() if k != "_total"} for r in rows]
        return result, total
    return [], 0


async def update_photo(conn: Any, photo_id: uuid.UUID, **fields: Any) -> dict | None:
    _ALLOWED = {"description"}
    set_parts: list[str] = []
    values: list[Any] = []
    idx = 1
    for field_name, value in fields.items():
        if field_name not in _ALLOWED:
            continue
        set_parts.append(f"{field_name} = ${idx}")
        values.append(value)
        idx += 1

    if not set_parts:
        return await find_photo_by_id(conn, photo_id)

    values.append(photo_id)
    query = (
        f"WITH updated AS ("
        f"  UPDATE album_photos SET {', '.join(set_parts)}, updated_at = NOW()"
        f"  WHERE id = ${idx} RETURNING *"
        f") SELECT updated.*, u.display_name AS uploaded_by_name"
        f" FROM updated LEFT JOIN users u ON u.id = updated.uploaded_by"
    )
    row = await conn.fetchrow(query, *values)
    if not row:
        return None
    return dict(row)


async def delete_photo(conn: Any, photo_id: uuid.UUID) -> bool:
    result = await conn.execute(
        "DELETE FROM album_photos WHERE id = $1",
        photo_id,
    )
    return bool(result == "DELETE 1")


async def count_photos(conn: Any, album_id: uuid.UUID) -> int:
    result = await conn.fetchval(
        "SELECT COUNT(*) FROM album_photos WHERE album_id = $1",
        album_id,
    )
    return int(result)


async def set_thumbnail_key(conn: Any, photo_id: uuid.UUID, thumbnail_key: str) -> bool:
    result = await conn.execute(
        "UPDATE album_photos SET thumbnail_key = $1, updated_at = NOW() WHERE id = $2",
        thumbnail_key,
        photo_id,
    )
    return bool(result == "UPDATE 1")


# ── Comments ────────────────────────────────────────────────────────────────


async def insert_comment(
    conn: Any,
    comment_id: uuid.UUID,
    album_id: uuid.UUID,
    photo_id: uuid.UUID | None,
    user_id: uuid.UUID,
    parent_id: uuid.UUID | None,
    content: str,
) -> dict:
    row = await conn.fetchrow(
        """
        INSERT INTO album_comments (id, album_id, photo_id, user_id, parent_id, content)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
        """,
        comment_id,
        album_id,
        photo_id,
        user_id,
        parent_id,
        content,
    )
    return dict(row)


async def find_comments(
    conn: Any,
    album_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    exclude_user_ids: list[uuid.UUID] | None = None,
) -> tuple[list[dict], int]:
    offset = (page - 1) * page_size
    exclusion_clause = ""
    params: list = [album_id, page_size, offset]
    if exclude_user_ids:
        exclusion_clause = " AND c.user_id != ALL($4::uuid[])"
        params.append(exclude_user_ids)
    rows = await conn.fetch(
        f"""
        SELECT c.*, u.display_name, u.avatar_url,
               COUNT(*) OVER() AS _total
        FROM album_comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.album_id = $1 AND c.is_deleted = false{exclusion_clause}
        ORDER BY c.created_at DESC
        LIMIT $2 OFFSET $3
        """,
        *params,
    )
    if rows:
        total = rows[0]["_total"]
        result = [{k: v for k, v in dict(r).items() if k != "_total"} for r in rows]
        return result, total
    return [], 0


async def delete_comment(conn: Any, comment_id: uuid.UUID) -> bool:
    result = await conn.execute(
        "UPDATE album_comments SET is_deleted = true, updated_at = NOW() "
        "WHERE id = $1 AND is_deleted = false",
        comment_id,
    )
    return bool(result == "UPDATE 1")


async def find_comment_by_id(conn: Any, comment_id: uuid.UUID) -> dict | None:
    row = await conn.fetchrow(
        "SELECT * FROM album_comments WHERE id = $1",
        comment_id,
    )
    return dict(row) if row else None


async def find_comment_by_id_with_user(conn: Any, comment_id: uuid.UUID) -> dict | None:
    """Fetch a single comment with user JOIN data (display_name, avatar_url)."""
    row = await conn.fetchrow(
        """
        SELECT c.*, u.display_name, u.avatar_url
        FROM album_comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.id = $1
        """,
        comment_id,
    )
    return dict(row) if row else None


async def find_member_by_id_with_user(
    conn: Any, album_id: uuid.UUID, user_id: uuid.UUID
) -> dict | None:
    """Fetch a single member with user JOIN data (display_name, username, avatar_url)."""
    row = await conn.fetchrow(
        """
        SELECT am.*, u.display_name, u.username, u.avatar_url
        FROM album_members am
        JOIN users u ON am.user_id = u.id
        WHERE am.album_id = $1 AND am.user_id = $2
        """,
        album_id,
        user_id,
    )
    return dict(row) if row else None
