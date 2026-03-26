"""Converters for album-related database rows to API response dicts."""

from app.converters.user_converter import async_resolve_avatar_url
from app.core.async_storage import generate_presigned_url
from app.repositories import file_scan_repo


async def to_album_response(row: dict) -> dict:
    """Convert an album DB row to an AlbumResponse-compatible dict."""
    cover_key = row.get("cover_photo_url")
    cover_url = None
    if cover_key:
        try:
            cover_url = await generate_presigned_url(cover_key, expires_in=900)
        except Exception:
            cover_url = None
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "description": row.get("description"),
        "cover_photo_url": cover_url,
        "created_by": str(row["created_by"]) if row.get("created_by") else None,
        "created_by_name": row.get("created_by_name"),
        "is_archived": row.get("is_archived", False),
        "photo_count": row.get("photo_count", 0),
        "member_count": row.get("member_count", 0),
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


async def to_album_photo_response(row: dict) -> dict:
    """Convert an album_photos DB row to an AlbumPhotoResponse-compatible dict."""
    storage_key = row.get("storage_key")
    thumbnail_key = row.get("thumbnail_key")

    storage_url = None
    thumbnail_url = None

    if storage_key and await file_scan_repo.is_clean(storage_key):
        try:
            storage_url = await generate_presigned_url(
                storage_key,
                expires_in=900,
                filename=row.get("original_filename"),
            )
        except Exception:
            storage_url = None

    if thumbnail_key:
        try:
            thumbnail_url = await generate_presigned_url(thumbnail_key, expires_in=900)
        except Exception:
            thumbnail_url = None

    return {
        "id": str(row["id"]),
        "album_id": str(row["album_id"]),
        "uploaded_by": str(row["uploaded_by"]) if row.get("uploaded_by") else None,
        "uploaded_by_name": row.get("uploaded_by_name"),
        "storage_url": storage_url,
        "thumbnail_url": thumbnail_url,
        "original_filename": row.get("original_filename"),
        "file_size_bytes": row.get("file_size_bytes", 0),
        "content_type": row.get("content_type"),
        "description": row.get("description"),
        "width": row.get("width"),
        "height": row.get("height"),
        "is_zip": row.get("is_zip", False),
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


async def to_album_member_response(row: dict) -> dict:
    """Convert an album_members + users JOIN row to AlbumMemberResponse-compatible dict."""
    return {
        "id": str(row["id"]),
        "album_id": str(row["album_id"]),
        "user_id": str(row["user_id"]),
        "display_name": row["display_name"],
        "username": row["username"],
        "avatar_url": await async_resolve_avatar_url(row.get("avatar_url")),
        "role": row["role"],
        "status": row["status"],
        "joined_at": row["joined_at"].isoformat(),
    }


async def to_album_comment_response(row: dict) -> dict:
    """Convert an album_comments + users JOIN row to AlbumCommentResponse-compatible dict."""
    return {
        "id": str(row["id"]),
        "album_id": str(row["album_id"]),
        "photo_id": str(row["photo_id"]) if row.get("photo_id") else None,
        "user_id": str(row["user_id"]),
        "display_name": row["display_name"],
        "avatar_url": await async_resolve_avatar_url(row.get("avatar_url")),
        "parent_id": str(row["parent_id"]) if row.get("parent_id") else None,
        "content": row["content"],
        "is_deleted": row.get("is_deleted", False),
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }
