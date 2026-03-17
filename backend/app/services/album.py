"""Album service — business logic for activity albums."""

import uuid

from loguru import logger

from app.converters.album_converter import (
    to_album_comment_response,
    to_album_member_response,
    to_album_photo_response,
    to_album_response,
)
from app.core.blacklist import get_blocked_user_ids
from app.core.config import settings
from app.core.constants import (
    ALBUM_ALLOWED_IMAGE_TYPES,
    ALBUM_ALLOWED_ZIP_TYPES,
    ALBUM_MAX_PHOTO_SIZE_BYTES,
    ALBUM_MAX_PHOTOS,
    ALBUM_MAX_ZIP_SIZE_BYTES,
)
from app.core.database import get_pool
from app.core.errors import AppError, ErrorCode
from app.core.file_validation import sanitize_html, validate_magic_number
from app.core.redis import get_redis
from app.repositories import album_repo, user_repo

# ── Albums ──────────────────────────────────────────────────────────────────


async def create_album(
    title: str,
    description: str | None,
    user_id: str,
) -> dict:
    """Create an album and auto-add creator as ADMIN member."""
    pool = get_pool()
    album_id = uuid.uuid4()
    user_uuid = uuid.UUID(user_id)

    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await album_repo.insert_album(conn, album_id, title, description, user_uuid)
            # Auto-add creator as ADMIN member with ACCEPTED status
            await album_repo.insert_member(
                conn,
                uuid.uuid4(),
                album_id,
                user_uuid,
                role="ADMIN",
                status="ACCEPTED",
            )
    logger.info("Album created", extra={"album_id": str(album_id), "user_id": user_id})
    # Re-fetch with JOINs for proper response
    async with pool.acquire() as conn:
        full_row = await album_repo.find_album_by_id(conn, album_id)
    if not full_row:
        return to_album_response(row)
    return to_album_response(full_row)


async def get_album(album_id: str) -> dict:
    """Get album by ID or raise 404."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await album_repo.find_album_by_id(conn, uuid.UUID(album_id))
    if not row:
        raise AppError(ErrorCode.ALBUM_001, 404, "Album not found.")
    return to_album_response(row)


async def list_albums(
    page: int = 1,
    page_size: int = 20,
    viewer_id: str | None = None,
) -> tuple[list[dict], int]:
    """List albums with pagination and blacklist filtering."""
    exclude: list[uuid.UUID] | None = None
    if viewer_id:
        try:
            redis = get_redis()
            blocked_ids = await get_blocked_user_ids(redis, viewer_id)
            if blocked_ids:
                exclude = [uuid.UUID(uid) for uid in blocked_ids]
        except Exception:
            pass
    pool = get_pool()
    async with pool.acquire() as conn:
        rows, total = await album_repo.find_albums(conn, page, page_size, exclude_user_ids=exclude)
    return [to_album_response(r) for r in rows], total


async def update_album(
    album_id: str,
    user_id: str,
    user_role: str,
    title: str | None = None,
    description: str | None = None,
) -> dict:
    """Update album. Creator or ADMIN/SUPER_ADMIN only."""
    pool = get_pool()
    album_uuid = uuid.UUID(album_id)

    async with pool.acquire() as conn:
        album = await album_repo.find_album_by_id(conn, album_uuid)
        if not album:
            raise AppError(ErrorCode.ALBUM_001, 404, "Album not found.")

        is_site_admin = user_role in ("ADMIN", "SUPER_ADMIN")
        is_creator = str(album["created_by"]) == user_id

        # Check album-level admin
        member = await album_repo.find_member(conn, album_uuid, uuid.UUID(user_id))
        is_album_admin = member and member["role"] == "ADMIN" and member["status"] == "ACCEPTED"

        if not (is_creator or is_site_admin or is_album_admin):
            raise AppError(ErrorCode.SYS_403, 403, "Not authorized to update this album.")

        fields: dict = {}
        if title is not None:
            fields["title"] = title
        if description is not None:
            fields["description"] = description

        row = await album_repo.update_album(conn, album_uuid, **fields)

    if not row:
        raise AppError(ErrorCode.ALBUM_001, 404, "Album not found.")
    return to_album_response(row)


async def delete_album(album_id: str, user_id: str, user_role: str) -> bool:
    """Soft-delete album with cascade cleanup of photos, comments, and members."""
    from app.core.async_storage import delete_file

    pool = get_pool()
    album_uuid = uuid.UUID(album_id)

    async with pool.acquire() as conn:
        album = await album_repo.find_album_by_id(conn, album_uuid)
        if not album:
            raise AppError(ErrorCode.ALBUM_001, 404, "Album not found.")

        is_creator = str(album["created_by"]) == user_id
        is_super_admin = user_role == "SUPER_ADMIN"

        if not (is_creator or is_super_admin):
            raise AppError(ErrorCode.SYS_403, 403, "Not authorized to delete this album.")

        async with conn.transaction():
            # 1. Collect photo data for storage cleanup and quota refund
            photos = await album_repo.find_all_photos_for_album(conn, album_uuid)

            # 2. Soft-delete the album
            deleted = await album_repo.soft_delete_album(conn, album_uuid)

            if deleted:
                # 3. Delete album comments
                await album_repo.delete_all_comments_for_album(conn, album_uuid)

                # 4. Refund storage quota per uploader
                quota_refunds: dict[uuid.UUID, int] = {}
                for photo in photos:
                    uploader = photo["uploaded_by"]
                    size = photo.get("file_size_bytes", 0)
                    if size > 0:
                        quota_refunds[uploader] = quota_refunds.get(uploader, 0) + size

                for uploader_id, total_size in quota_refunds.items():
                    await conn.execute(
                        "UPDATE users SET storage_used_bytes = "
                        "GREATEST(storage_used_bytes - $1, 0) WHERE id = $2",
                        total_size,
                        uploader_id,
                    )

                # 5. Delete album photos from DB
                await album_repo.delete_all_photos_for_album(conn, album_uuid)

                # 6. Delete album members
                await album_repo.delete_all_members_for_album(conn, album_uuid)

    # 7. Best-effort storage cleanup (outside transaction)
    if deleted:
        for photo in photos:
            for key_field in ("storage_key", "thumbnail_key"):
                key = photo.get(key_field)
                if key:
                    try:
                        await delete_file(key)
                    except Exception:
                        logger.warning(
                            "Failed to delete photo file from storage during album cleanup",
                            extra={"album_id": album_id, "key": key},
                        )

    logger.info("Album deleted", extra={"album_id": album_id, "user_id": user_id})
    return deleted


# ── Members ─────────────────────────────────────────────────────────────────


async def add_member(
    album_id: str,
    user_id: str,
    target_user_id: str,
    user_role: str,
) -> dict:
    """ADMIN/creator adds a member directly with ACCEPTED status."""
    pool = get_pool()
    album_uuid = uuid.UUID(album_id)
    user_uuid = uuid.UUID(user_id)
    target_uuid = uuid.UUID(target_user_id)

    async with pool.acquire() as conn:
        album = await album_repo.find_album_by_id(conn, album_uuid)
        if not album:
            raise AppError(ErrorCode.ALBUM_001, 404, "Album not found.")

        is_site_admin = user_role in ("ADMIN", "SUPER_ADMIN")
        is_creator = str(album["created_by"]) == user_id
        member = await album_repo.find_member(conn, album_uuid, user_uuid)
        is_album_admin = member and member["role"] == "ADMIN" and member["status"] == "ACCEPTED"

        if not (is_creator or is_site_admin or is_album_admin):
            raise AppError(ErrorCode.SYS_403, 403, "Not authorized to add members.")

        # Check target not already member
        existing = await album_repo.find_member(conn, album_uuid, target_uuid)
        if existing:
            raise AppError(
                ErrorCode.SYS_409, 409, "User is already a member or has a pending request."
            )

        member_row = await album_repo.insert_member(
            conn, uuid.uuid4(), album_uuid, target_uuid, role="MEMBER", status="ACCEPTED"
        )

    logger.info(
        "Album member added",
        extra={"album_id": album_id, "target_user_id": target_user_id},
    )
    # Return with user info via direct lookup
    pool = get_pool()
    async with pool.acquire() as conn:
        full_row = await album_repo.find_member_by_id_with_user(conn, album_uuid, target_uuid)
        if full_row:
            return to_album_member_response(full_row)
    return {"id": str(member_row["id"]), "status": "ACCEPTED"}


async def join_album(album_id: str, user_id: str) -> dict:
    """User requests to join an album (PENDING status)."""
    pool = get_pool()
    album_uuid = uuid.UUID(album_id)
    user_uuid = uuid.UUID(user_id)

    async with pool.acquire() as conn:
        album = await album_repo.find_album_by_id(conn, album_uuid)
        if not album:
            raise AppError(ErrorCode.ALBUM_001, 404, "Album not found.")

        if album.get("is_archived"):
            raise AppError(ErrorCode.ALBUM_001, 400, "Album is archived.")

        existing = await album_repo.find_member(conn, album_uuid, user_uuid)
        if existing:
            raise AppError(ErrorCode.SYS_409, 409, "Already a member or request pending.")

        member_row = await album_repo.insert_member(
            conn, uuid.uuid4(), album_uuid, user_uuid, role="MEMBER", status="PENDING"
        )

    logger.info("Album join requested", extra={"album_id": album_id, "user_id": user_id})
    return {"id": str(member_row["id"]), "status": "PENDING"}


async def approve_member(
    album_id: str,
    user_id: str,
    member_id: str,
    user_role: str,
) -> bool:
    """Approve a pending membership request."""
    pool = get_pool()
    album_uuid = uuid.UUID(album_id)
    user_uuid = uuid.UUID(user_id)
    member_uuid = uuid.UUID(member_id)

    async with pool.acquire() as conn:
        album = await album_repo.find_album_by_id(conn, album_uuid)
        if not album:
            raise AppError(ErrorCode.ALBUM_001, 404, "Album not found.")

        is_site_admin = user_role in ("ADMIN", "SUPER_ADMIN")
        is_creator = str(album["created_by"]) == user_id
        member = await album_repo.find_member(conn, album_uuid, user_uuid)
        is_album_admin = member and member["role"] == "ADMIN" and member["status"] == "ACCEPTED"

        if not (is_creator or is_site_admin or is_album_admin):
            raise AppError(ErrorCode.SYS_403, 403, "Not authorized to approve members.")

        updated = await album_repo.update_member_status(conn, member_uuid, "ACCEPTED")

    return updated


async def remove_member(
    album_id: str,
    user_id: str,
    target_user_id: str,
    user_role: str,
) -> bool:
    """Remove a member (self-leave or admin-remove)."""
    pool = get_pool()
    album_uuid = uuid.UUID(album_id)
    user_uuid = uuid.UUID(user_id)
    target_uuid = uuid.UUID(target_user_id)

    is_self_leave = user_id == target_user_id

    async with pool.acquire() as conn:
        album = await album_repo.find_album_by_id(conn, album_uuid)
        if not album:
            raise AppError(ErrorCode.ALBUM_001, 404, "Album not found.")

        if not is_self_leave:
            is_site_admin = user_role in ("ADMIN", "SUPER_ADMIN")
            is_creator = str(album["created_by"]) == user_id
            member = await album_repo.find_member(conn, album_uuid, user_uuid)
            is_album_admin = member and member["role"] == "ADMIN" and member["status"] == "ACCEPTED"

            if not (is_creator or is_site_admin or is_album_admin):
                raise AppError(ErrorCode.SYS_403, 403, "Not authorized to remove members.")

        deleted = await album_repo.delete_member(conn, album_uuid, target_uuid)

    return deleted


async def list_members(
    album_id: str,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """List album members with pagination."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows, total = await album_repo.find_members(conn, uuid.UUID(album_id), page, page_size)
    return [to_album_member_response(r) for r in rows], total


# ── Photos ──────────────────────────────────────────────────────────────────


async def upload_photo(
    album_id: str,
    user_id: str,
    file_data: bytes,
    filename: str,
    content_type: str,
) -> dict:
    """Upload a photo to an album."""
    from app.core.async_storage import upload_file as async_upload_file
    from app.core.storage import album_photo_key, album_thumbnail_key

    pool = get_pool()
    album_uuid = uuid.UUID(album_id)
    user_uuid = uuid.UUID(user_id)

    # 1. Validate file type
    if content_type not in ALBUM_ALLOWED_IMAGE_TYPES:
        raise AppError(
            ErrorCode.ALBUM_003,
            400,
            f"File type not allowed. Accepted: {', '.join(ALBUM_ALLOWED_IMAGE_TYPES)}",
        )

    # 2. Validate magic bytes
    if not validate_magic_number(file_data, content_type):
        raise AppError(
            ErrorCode.ALBUM_003,
            400,
            "File content does not match its declared type.",
        )

    # 3. Validate file size
    file_size = len(file_data)
    if file_size > ALBUM_MAX_PHOTO_SIZE_BYTES:
        raise AppError(
            ErrorCode.ALBUM_002,
            400,
            f"File size exceeds {ALBUM_MAX_PHOTO_SIZE_BYTES // (1024 * 1024)}MB limit.",
        )

    async with pool.acquire() as conn:
        async with conn.transaction():
            # 4. Check album exists and membership
            album = await album_repo.find_album_by_id(conn, album_uuid)
            if not album:
                raise AppError(ErrorCode.ALBUM_001, 404, "Album not found.")

            member = await album_repo.find_member(conn, album_uuid, user_uuid)
            if not member or member["status"] != "ACCEPTED":
                raise AppError(
                    ErrorCode.SYS_403, 403, "Must be an approved album member to upload."
                )

            # 5. Check album photo count
            photo_count = await album_repo.count_photos(conn, album_uuid)
            if photo_count >= ALBUM_MAX_PHOTOS:
                raise AppError(
                    ErrorCode.ALBUM_002,
                    400,
                    f"Album has reached the maximum of {ALBUM_MAX_PHOTOS} photos.",
                )

            # 6. Check user storage quota (FOR UPDATE to prevent race condition)
            quota_row = await conn.fetchrow(
                "SELECT storage_used_bytes FROM users WHERE id = $1 FOR UPDATE",
                user_uuid,
            )
            storage_used = int(quota_row["storage_used_bytes"]) if quota_row else 0
            if storage_used + file_size > settings.MAX_USER_STORAGE_BYTES:
                raise AppError(
                    ErrorCode.ALBUM_002,
                    400,
                    "Storage quota exceeded.",
                )

            # 7. Upload to MinIO
            ext = ""
            if "." in filename:
                ext = filename.rsplit(".", 1)[-1].lower()
            file_uuid = str(uuid.uuid4())
            storage_key = album_photo_key(album_id, file_uuid, ext)
            await async_upload_file(file_data, storage_key, content_type)

            # 8. Increment storage used (within same transaction)
            await conn.execute(
                "UPDATE users SET storage_used_bytes = storage_used_bytes + $1 WHERE id = $2",
                file_size,
                user_uuid,
            )

            # 9. Insert photo record
            photo_id = uuid.uuid4()
            row = await album_repo.insert_photo(
                conn,
                photo_id,
                album_uuid,
                user_uuid,
                storage_key,
                filename,
                file_size,
                content_type,
            )

    # 10. Dispatch thumbnail generation (lazy import)
    try:
        thumb_key = album_thumbnail_key(album_id, file_uuid)
        from app.tasks.thumbnail import generate_thumbnail_task

        generate_thumbnail_task.delay(storage_key, thumb_key, str(photo_id))
    except Exception:
        logger.warning(
            "Failed to dispatch thumbnail task",
            extra={"photo_id": str(photo_id)},
        )

    logger.info(
        "Album photo uploaded",
        extra={"album_id": album_id, "photo_id": str(photo_id), "size": file_size},
    )

    # Re-fetch for full response with JOINed data
    async with pool.acquire() as conn:
        full_row = await album_repo.find_photo_by_id(conn, photo_id)
    return to_album_photo_response(full_row or row)


async def upload_file_zip(
    album_id: str,
    user_id: str,
    file_data: bytes,
    filename: str,
    content_type: str,
) -> dict:
    """Upload a ZIP file to an album (no thumbnail)."""
    from app.core.storage import album_zip_key

    pool = get_pool()
    album_uuid = uuid.UUID(album_id)
    user_uuid = uuid.UUID(user_id)

    # Validate type
    if content_type not in ALBUM_ALLOWED_ZIP_TYPES:
        raise AppError(
            ErrorCode.ALBUM_003,
            400,
            "Only ZIP files are allowed for file uploads.",
        )

    # Validate magic bytes
    if not validate_magic_number(file_data, "application/zip"):
        # ZIP and DOCX share PK signature, use the generic check
        if not file_data[:4] == b"PK\x03\x04":
            raise AppError(
                ErrorCode.ALBUM_003,
                400,
                "File content does not match ZIP format.",
            )

    file_size = len(file_data)
    if file_size > ALBUM_MAX_ZIP_SIZE_BYTES:
        raise AppError(
            ErrorCode.ALBUM_002,
            400,
            f"ZIP file size exceeds {ALBUM_MAX_ZIP_SIZE_BYTES // (1024 * 1024)}MB limit.",
        )

    async with pool.acquire() as conn:
        album = await album_repo.find_album_by_id(conn, album_uuid)
        if not album:
            raise AppError(ErrorCode.ALBUM_001, 404, "Album not found.")

        member = await album_repo.find_member(conn, album_uuid, user_uuid)
        if not member or member["status"] != "ACCEPTED":
            raise AppError(ErrorCode.SYS_403, 403, "Must be an approved album member to upload.")

        async with conn.transaction():
            # Lock user row to prevent concurrent uploads bypassing quota
            quota_row = await conn.fetchrow(
                "SELECT storage_used_bytes FROM users WHERE id = $1 FOR UPDATE",
                user_uuid,
            )
            storage_used = int(quota_row["storage_used_bytes"]) if quota_row else 0
            if storage_used + file_size > settings.MAX_USER_STORAGE_BYTES:
                raise AppError(ErrorCode.ALBUM_002, 400, "Storage quota exceeded.")

            ext = ""
            if "." in filename:
                ext = filename.rsplit(".", 1)[-1].lower()
            file_uuid = str(uuid.uuid4())
            storage_key = album_zip_key(album_id, file_uuid, ext)

            # Use async storage to avoid blocking the event loop
            from app.core.async_storage import upload_file as async_upload_file

            await async_upload_file(file_data, storage_key, content_type)

            # Increment storage within same transaction
            await conn.execute(
                "UPDATE users SET storage_used_bytes = storage_used_bytes + $1 WHERE id = $2",
                file_size,
                user_uuid,
            )

            photo_id = uuid.uuid4()
            row = await album_repo.insert_photo(
                conn,
                photo_id,
                album_uuid,
                user_uuid,
                storage_key,
                filename,
                file_size,
                content_type,
                is_zip=True,
            )

    logger.info(
        "Album ZIP uploaded",
        extra={"album_id": album_id, "photo_id": str(photo_id), "size": file_size},
    )

    async with pool.acquire() as conn:
        full_row = await album_repo.find_photo_by_id(conn, photo_id)
    return to_album_photo_response(full_row or row)


async def get_photo(album_id: str, photo_id: str) -> dict:
    """Get a single photo with presigned URL."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await album_repo.find_photo_by_id(conn, uuid.UUID(photo_id))
    if not row or str(row["album_id"]) != album_id:
        raise AppError(ErrorCode.ALBUM_001, 404, "Photo not found.")
    return to_album_photo_response(row)


async def list_photos(
    album_id: str,
    page: int = 1,
    page_size: int = 20,
    viewer_id: str | None = None,
) -> tuple[list[dict], int]:
    """List photos in an album with pagination and blacklist filtering."""
    exclude: list[uuid.UUID] | None = None
    if viewer_id:
        try:
            redis = get_redis()
            blocked_ids = await get_blocked_user_ids(redis, viewer_id)
            if blocked_ids:
                exclude = [uuid.UUID(uid) for uid in blocked_ids]
        except Exception:
            pass
    pool = get_pool()
    async with pool.acquire() as conn:
        rows, total = await album_repo.find_photos(
            conn,
            uuid.UUID(album_id),
            page,
            page_size,
            exclude_user_ids=exclude,
        )
    return [to_album_photo_response(r) for r in rows], total


async def update_photo(
    album_id: str,
    photo_id: str,
    user_id: str,
    user_role: str,
    description: str | None = None,
) -> dict:
    """Update photo description. Uploader or album ADMIN."""
    pool = get_pool()
    album_uuid = uuid.UUID(album_id)
    photo_uuid = uuid.UUID(photo_id)

    async with pool.acquire() as conn:
        photo = await album_repo.find_photo_by_id(conn, photo_uuid)
        if not photo or str(photo["album_id"]) != album_id:
            raise AppError(ErrorCode.ALBUM_001, 404, "Photo not found.")

        is_uploader = str(photo["uploaded_by"]) == user_id
        is_site_admin = user_role in ("ADMIN", "SUPER_ADMIN")
        member = await album_repo.find_member(conn, album_uuid, uuid.UUID(user_id))
        is_album_admin = member and member["role"] == "ADMIN" and member["status"] == "ACCEPTED"

        if not (is_uploader or is_site_admin or is_album_admin):
            raise AppError(ErrorCode.SYS_403, 403, "Not authorized to update this photo.")

        row = await album_repo.update_photo(conn, photo_uuid, description=description)

    if not row:
        raise AppError(ErrorCode.ALBUM_001, 404, "Photo not found.")
    return to_album_photo_response(row)


async def delete_photo(
    album_id: str,
    photo_id: str,
    user_id: str,
    user_role: str,
) -> bool:
    """Delete a photo. Album creator, uploader, or site ADMIN/SUPER_ADMIN."""
    from app.core.async_storage import delete_file

    pool = get_pool()
    album_uuid = uuid.UUID(album_id)
    photo_uuid = uuid.UUID(photo_id)

    async with pool.acquire() as conn:
        photo = await album_repo.find_photo_by_id(conn, photo_uuid)
        if not photo or str(photo["album_id"]) != album_id:
            raise AppError(ErrorCode.ALBUM_001, 404, "Photo not found.")

        album = await album_repo.find_album_by_id(conn, album_uuid)
        is_uploader = str(photo["uploaded_by"]) == user_id
        is_creator = album and str(album["created_by"]) == user_id
        is_site_admin = user_role in ("ADMIN", "SUPER_ADMIN")

        if not (is_uploader or is_creator or is_site_admin):
            raise AppError(ErrorCode.SYS_403, 403, "Not authorized to delete this photo.")

        # Delete from MinIO (best-effort)
        storage_key = photo.get("storage_key")
        thumbnail_key = photo.get("thumbnail_key")
        try:
            if storage_key:
                await delete_file(storage_key)
            if thumbnail_key:
                await delete_file(thumbnail_key)
        except Exception:
            logger.warning(
                "Failed to delete photo files from storage",
                extra={"photo_id": photo_id},
            )

        # Refund storage quota
        file_size = photo.get("file_size_bytes", 0)
        uploaded_by = photo["uploaded_by"]
        if file_size > 0:
            await user_repo.decrement_storage_used(uploaded_by, file_size)

        deleted = await album_repo.delete_photo(conn, photo_uuid)

    return deleted


# ── Comments ────────────────────────────────────────────────────────────────


async def create_comment(
    album_id: str,
    user_id: str,
    content: str,
    photo_id: str | None = None,
    parent_id: str | None = None,
) -> dict:
    """Create a comment on an album or photo."""
    pool = get_pool()
    album_uuid = uuid.UUID(album_id)
    user_uuid = uuid.UUID(user_id)
    photo_uuid = uuid.UUID(photo_id) if photo_id else None
    parent_uuid = uuid.UUID(parent_id) if parent_id else None

    sanitized_content = sanitize_html(content)

    async with pool.acquire() as conn:
        album = await album_repo.find_album_by_id(conn, album_uuid)
        if not album:
            raise AppError(ErrorCode.ALBUM_001, 404, "Album not found.")

        comment_id = uuid.uuid4()
        row = await album_repo.insert_comment(
            conn,
            comment_id,
            album_uuid,
            photo_uuid,
            user_uuid,
            parent_uuid,
            sanitized_content,
        )

    logger.info(
        "Album comment created",
        extra={"album_id": album_id, "comment_id": str(comment_id)},
    )
    # Re-fetch with user JOINs via direct ID lookup
    async with pool.acquire() as conn:
        full_row = await album_repo.find_comment_by_id_with_user(conn, comment_id)
        if full_row:
            return to_album_comment_response(full_row)

    # Fallback
    return {
        "id": str(row["id"]),
        "album_id": str(row["album_id"]),
        "photo_id": str(row["photo_id"]) if row.get("photo_id") else None,
        "user_id": str(row["user_id"]),
        "display_name": "",
        "avatar_url": None,
        "parent_id": str(row["parent_id"]) if row.get("parent_id") else None,
        "content": row["content"],
        "is_deleted": False,
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


async def list_comments(
    album_id: str,
    page: int = 1,
    page_size: int = 20,
    viewer_id: str | None = None,
) -> tuple[list[dict], int]:
    """List comments on an album."""
    pool = get_pool()
    album_uuid = uuid.UUID(album_id)

    # Check album exists
    async with pool.acquire() as conn:
        album = await album_repo.find_album_by_id(conn, album_uuid)
    if not album:
        raise AppError(ErrorCode.ALBUM_001, 404, "Album not found.")

    exclude: list[uuid.UUID] | None = None
    if viewer_id:
        try:
            redis = get_redis()
            blocked_ids = await get_blocked_user_ids(redis, viewer_id)
            if blocked_ids:
                exclude = [uuid.UUID(uid) for uid in blocked_ids]
        except Exception:
            pass
    async with pool.acquire() as conn:
        rows, total = await album_repo.find_comments(
            conn,
            album_uuid,
            page,
            page_size,
            exclude_user_ids=exclude,
        )
    return [to_album_comment_response(r) for r in rows], total


async def delete_comment(
    album_id: str,
    comment_id: str,
    user_id: str,
    user_role: str,
) -> bool:
    """Delete a comment. Author or ADMIN."""
    pool = get_pool()
    album_uuid = uuid.UUID(album_id)
    comment_uuid = uuid.UUID(comment_id)

    async with pool.acquire() as conn:
        comment = await album_repo.find_comment_by_id(conn, comment_uuid)
        if not comment or str(comment["album_id"]) != album_id:
            raise AppError(ErrorCode.ALBUM_001, 404, "Comment not found.")

        is_author = str(comment["user_id"]) == user_id
        is_site_admin = user_role in ("ADMIN", "SUPER_ADMIN")
        member = await album_repo.find_member(conn, album_uuid, uuid.UUID(user_id))
        is_album_admin = member and member["role"] == "ADMIN" and member["status"] == "ACCEPTED"

        if not (is_author or is_site_admin or is_album_admin):
            raise AppError(ErrorCode.SYS_403, 403, "Not authorized to delete this comment.")

        deleted = await album_repo.delete_comment(conn, comment_uuid)

    return deleted
