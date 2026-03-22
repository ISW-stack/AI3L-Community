"""Album service — business logic for activity albums."""

import uuid
from typing import Any

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
    ALBUM_MAX_COVER_SIZE_BYTES,
    ALBUM_MAX_PHOTO_SIZE_BYTES,
    ALBUM_MAX_PHOTOS,
    ALBUM_MAX_ZIP_SIZE_BYTES,
)
from app.core.database import get_pool
from app.core.errors import AppError, ErrorCode
from app.core.file_validation import sanitize_html, validate_magic_number
from app.core.redis import get_redis
from app.repositories import album_repo, user_repo

_UNSET: Any = object()  # sentinel — distinguishes "not provided" from "set to None"

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
    title: Any = _UNSET,
    description: Any = _UNSET,
) -> dict:
    """Update album. Creator or ADMIN/SUPER_ADMIN only."""
    pool = get_pool()
    album_uuid = uuid.UUID(album_id)

    async with pool.acquire() as conn:
        async with conn.transaction():
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
            if title is not _UNSET:
                fields["title"] = title
            if description is not _UNSET:
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
        is_site_admin = user_role in ("ADMIN", "SUPER_ADMIN")

        if not (is_creator or is_site_admin):
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
        # Delete dedicated cover file if it exists
        cover_key = album.get("cover_photo_url")
        if cover_key and "/cover/" in cover_key:
            try:
                await delete_file(cover_key)
            except Exception:
                logger.warning(
                    "Failed to delete cover file during album cleanup",
                    extra={"album_id": album_id, "key": cover_key},
                )

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


# ── Cover ──────────────────────────────────────────────────────────────────


async def set_cover_from_photo(
    album_id: str,
    photo_id: str,
    user_id: str,
    user_role: str,
) -> dict:
    """Set an existing album photo as the album cover."""
    pool = get_pool()
    album_uuid = uuid.UUID(album_id)
    photo_uuid = uuid.UUID(photo_id)

    async with pool.acquire() as conn:
        album = await album_repo.find_album_by_id(conn, album_uuid)
        if not album:
            raise AppError(ErrorCode.ALBUM_001, 404, "Album not found.")

        _check_album_admin(
            album,
            user_id,
            user_role,
            await album_repo.find_member(conn, album_uuid, uuid.UUID(user_id)),
        )

        photo = await album_repo.find_photo_by_id(conn, photo_uuid)
        if not photo or str(photo["album_id"]) != album_id:
            raise AppError(ErrorCode.ALBUM_001, 404, "Photo not found in this album.")

        await album_repo.set_cover_photo(conn, album_uuid, photo["storage_key"])

    async with pool.acquire() as conn:
        row = await album_repo.find_album_by_id(conn, album_uuid)
    return to_album_response(row or album)


async def upload_cover(
    album_id: str,
    user_id: str,
    user_role: str,
    file_data: bytes,
    filename: str,
    content_type: str,
) -> dict:
    """Upload a new image as album cover. Counts toward uploader's storage quota."""
    from app.core.async_storage import delete_file
    from app.core.async_storage import upload_file as async_upload_file
    from app.core.storage import album_cover_key

    album_uuid = uuid.UUID(album_id)
    user_uuid = uuid.UUID(user_id)

    # Validate file type
    if content_type not in ALBUM_ALLOWED_IMAGE_TYPES:
        raise AppError(
            ErrorCode.ALBUM_003,
            400,
            f"File type not allowed. Accepted: {', '.join(ALBUM_ALLOWED_IMAGE_TYPES)}",
        )

    # Validate magic bytes
    if not validate_magic_number(file_data, content_type):
        raise AppError(ErrorCode.ALBUM_003, 400, "File content does not match its declared type.")

    file_size = len(file_data)
    if file_size > ALBUM_MAX_COVER_SIZE_BYTES:
        raise AppError(
            ErrorCode.ALBUM_002,
            400,
            f"Cover image size exceeds {ALBUM_MAX_COVER_SIZE_BYTES // (1024 * 1024)}MB limit.",
        )

    pool = get_pool()

    # Phase 1: Validate permissions (no quota lock needed yet)
    async with pool.acquire() as conn:
        album = await album_repo.find_album_by_id(conn, album_uuid)
        if not album:
            raise AppError(ErrorCode.ALBUM_001, 404, "Album not found.")

        _check_album_admin(
            album, user_id, user_role, await album_repo.find_member(conn, album_uuid, user_uuid)
        )

    # Phase 2: Upload to MinIO (outside transaction — not transactional)
    ext = ""
    if "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
    file_uuid = str(uuid.uuid4())
    storage_key = album_cover_key(album_id, file_uuid, ext)
    await async_upload_file(file_data, storage_key, content_type)

    # Phase 3: Quota check + increment + DB update in ONE transaction (FOR UPDATE
    # serializes concurrent requests so the quota cannot be bypassed).
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Lock user row and verify quota
                quota_row = await conn.fetchrow(
                    "SELECT storage_used_bytes FROM users WHERE id = $1 FOR UPDATE",
                    user_uuid,
                )
                storage_used = int(quota_row["storage_used_bytes"]) if quota_row else 0
                if storage_used + file_size > settings.MAX_USER_STORAGE_BYTES:
                    # Clean up the already-uploaded MinIO file
                    try:
                        await delete_file(storage_key)
                    except Exception:
                        logger.warning(
                            "Failed to clean up cover after quota rejection",
                            extra={"key": storage_key},
                        )
                    raise AppError(ErrorCode.ALBUM_002, 400, "Storage quota exceeded.")

                # Delete old cover file from storage if it was a dedicated cover (not a photo key)
                old_cover_key = album.get("cover_photo_url")
                if old_cover_key and "/cover/" in old_cover_key:
                    try:
                        await delete_file(old_cover_key)
                    except Exception:
                        logger.warning("Failed to delete old cover", extra={"key": old_cover_key})

                # Increment storage
                await conn.execute(
                    "UPDATE users SET storage_used_bytes = storage_used_bytes + $1 WHERE id = $2",
                    file_size,
                    user_uuid,
                )

                await album_repo.set_cover_photo(conn, album_uuid, storage_key)
    except AppError:
        raise
    except Exception:
        # DB failed after MinIO upload succeeded — clean up orphaned file
        logger.error(
            "DB update failed after cover upload, cleaning up MinIO file",
            extra={"album_id": album_id, "key": storage_key},
            exc_info=True,
        )
        try:
            await delete_file(storage_key)
        except Exception:
            logger.error(
                "Failed to clean up orphaned cover file from MinIO",
                extra={"key": storage_key},
                exc_info=True,
            )
        raise AppError(ErrorCode.SYS_500, 500, "Failed to update album cover. Please try again.")

    logger.info("Album cover uploaded", extra={"album_id": album_id, "user_id": user_id})

    async with pool.acquire() as conn:
        row = await album_repo.find_album_by_id(conn, album_uuid)
    return to_album_response(row or album)


def _check_album_admin(album: dict, user_id: str, user_role: str, member: dict | None) -> None:
    """Check if user is album creator, album admin, or site admin."""
    is_site_admin = user_role in ("ADMIN", "SUPER_ADMIN")
    is_creator = str(album["created_by"]) == user_id
    is_album_admin = member and member["role"] == "ADMIN" and member["status"] == "ACCEPTED"
    if not (is_creator or is_site_admin or is_album_admin):
        raise AppError(ErrorCode.SYS_403, 403, "Not authorized to update this album.")


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
        async with conn.transaction():
            album = await album_repo.find_album_by_id(conn, album_uuid)
            if not album:
                raise AppError(ErrorCode.ALBUM_001, 404, "Album not found.")

            is_site_admin = user_role in ("ADMIN", "SUPER_ADMIN")
            is_creator = str(album["created_by"]) == user_id
            member = await album_repo.find_member(conn, album_uuid, user_uuid)
            is_album_admin = member and member["role"] == "ADMIN" and member["status"] == "ACCEPTED"

            if not (is_creator or is_site_admin or is_album_admin):
                raise AppError(ErrorCode.SYS_403, 403, "Not authorized to add members.")

            # Check target not already member (inside transaction for atomicity)
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
        async with conn.transaction():
            album = await album_repo.find_album_by_id(conn, album_uuid)
            if not album:
                raise AppError(ErrorCode.ALBUM_001, 404, "Album not found.")

            if album.get("is_archived"):
                raise AppError(ErrorCode.ALBUM_001, 400, "Album is archived.")

            # Check + insert inside transaction for atomicity
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

        updated = await album_repo.update_member_status(
            conn,
            member_uuid,
            "ACCEPTED",
            album_id=album_uuid,
            required_current_status="PENDING",
        )
        if not updated:
            raise AppError(ErrorCode.ALBUM_001, 404, "Pending member not found in this album.")

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

    # Phase 1: Validate permissions and check limits (short read transaction)
    async with pool.acquire() as conn:
        # 4. Check album exists and membership
        album = await album_repo.find_album_by_id(conn, album_uuid)
        if not album:
            raise AppError(ErrorCode.ALBUM_001, 404, "Album not found.")

        member = await album_repo.find_member(conn, album_uuid, user_uuid)
        if not member or member["status"] != "ACCEPTED":
            raise AppError(ErrorCode.SYS_403, 403, "Must be an approved album member to upload.")

        # 5. Check album photo count (advisory — exact enforcement via FOR UPDATE below)
        photo_count = await album_repo.count_photos(conn, album_uuid)
        if photo_count >= ALBUM_MAX_PHOTOS:
            raise AppError(
                ErrorCode.ALBUM_002,
                400,
                f"Album has reached the maximum of {ALBUM_MAX_PHOTOS} photos.",
            )

    # Phase 2: Upload to MinIO outside any transaction
    ext = ""
    if "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
    file_uuid = str(uuid.uuid4())
    storage_key = album_photo_key(album_id, file_uuid, ext)
    await async_upload_file(file_data, storage_key, content_type)

    # Phase 3: Quota check + increment + DB insert in one short transaction
    photo_id = uuid.uuid4()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # 6. Lock user row to prevent concurrent uploads bypassing quota
                quota_row = await conn.fetchrow(
                    "SELECT storage_used_bytes FROM users WHERE id = $1 FOR UPDATE",
                    user_uuid,
                )
                storage_used = int(quota_row["storage_used_bytes"]) if quota_row else 0
                if storage_used + file_size > settings.MAX_USER_STORAGE_BYTES:
                    # Clean up the already-uploaded MinIO file
                    try:
                        from app.core.async_storage import delete_file

                        await delete_file(storage_key)
                    except Exception:
                        logger.warning(
                            "Failed to clean up photo after quota rejection",
                            extra={"key": storage_key},
                        )
                    raise AppError(ErrorCode.ALBUM_002, 400, "Storage quota exceeded.")

                # 7. Increment storage used
                await conn.execute(
                    "UPDATE users SET storage_used_bytes = storage_used_bytes + $1 WHERE id = $2",
                    file_size,
                    user_uuid,
                )

                # 8. Insert photo record
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

                # 9. Auto-set as cover if album has no cover yet
                if not album.get("cover_photo_url"):
                    await album_repo.set_cover_photo(conn, album_uuid, storage_key)
    except AppError:
        raise
    except Exception:
        # DB failed after MinIO upload succeeded — clean up orphaned file
        logger.error(
            "DB insert failed after photo upload, cleaning up MinIO file",
            extra={"album_id": album_id, "key": storage_key},
            exc_info=True,
        )
        try:
            from app.core.async_storage import delete_file

            await delete_file(storage_key)
        except Exception:
            logger.error(
                "Failed to clean up orphaned photo file from MinIO",
                extra={"key": storage_key},
                exc_info=True,
            )
        raise AppError(ErrorCode.SYS_500, 500, "Failed to save photo. Please try again.")

    # 11. Dispatch thumbnail generation (lazy import)
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
    """Upload a ZIP file to an album (no thumbnail).

    Security: validates ZIP structure, checks for zip bombs, strips Mac junk,
    blocks path traversal and dangerous file types.
    """
    from app.core.storage import album_zip_key
    from app.core.zip_validation import validate_zip

    pool = get_pool()
    album_uuid = uuid.UUID(album_id)
    user_uuid = uuid.UUID(user_id)

    # 1. Validate content type
    if content_type not in ALBUM_ALLOWED_ZIP_TYPES:
        raise AppError(
            ErrorCode.ALBUM_003,
            400,
            "Only ZIP files are allowed for file uploads.",
        )

    # 2. Validate compressed size
    file_size = len(file_data)
    if file_size > ALBUM_MAX_ZIP_SIZE_BYTES:
        raise AppError(
            ErrorCode.ALBUM_002,
            400,
            f"ZIP file size exceeds {ALBUM_MAX_ZIP_SIZE_BYTES // (1024 * 1024)}MB limit.",
        )

    # 3. Comprehensive ZIP security validation (bomb, traversal, junk, extensions)
    result = validate_zip(file_data, strip_mac_junk=True)
    upload_data = result.clean_data or file_data
    upload_size = len(upload_data)

    if result.stripped_entries:
        logger.info(
            "Stripped Mac junk from ZIP",
            extra={
                "album_id": album_id,
                "stripped_count": len(result.stripped_entries),
            },
        )

    from app.core.async_storage import upload_file as async_upload_file

    # Phase 1: Validate permissions and check limits (short read transaction)
    async with pool.acquire() as conn:
        album = await album_repo.find_album_by_id(conn, album_uuid)
        if not album:
            raise AppError(ErrorCode.ALBUM_001, 404, "Album not found.")

        member = await album_repo.find_member(conn, album_uuid, user_uuid)
        if not member or member["status"] != "ACCEPTED":
            raise AppError(ErrorCode.SYS_403, 403, "Must be an approved album member to upload.")

        # Check album photo count (advisory — exact enforcement via FOR UPDATE below)
        photo_count = await album_repo.count_photos(conn, album_uuid)
        if photo_count >= ALBUM_MAX_PHOTOS:
            raise AppError(
                ErrorCode.ALBUM_002,
                400,
                f"Album has reached the maximum of {ALBUM_MAX_PHOTOS} photos.",
            )

    # Phase 2: Upload to MinIO outside any transaction
    ext = ""
    if "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
    file_uuid = str(uuid.uuid4())
    storage_key = album_zip_key(album_id, file_uuid, ext)
    await async_upload_file(upload_data, storage_key, content_type)

    # Phase 3: Quota check + increment + DB insert in one short transaction
    photo_id = uuid.uuid4()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Lock user row to prevent concurrent uploads bypassing quota
                quota_row = await conn.fetchrow(
                    "SELECT storage_used_bytes FROM users WHERE id = $1 FOR UPDATE",
                    user_uuid,
                )
                storage_used = int(quota_row["storage_used_bytes"]) if quota_row else 0
                if storage_used + upload_size > settings.MAX_USER_STORAGE_BYTES:
                    # Clean up the already-uploaded MinIO file
                    try:
                        from app.core.async_storage import delete_file

                        await delete_file(storage_key)
                    except Exception:
                        logger.warning(
                            "Failed to clean up ZIP after quota rejection",
                            extra={"key": storage_key},
                        )
                    raise AppError(ErrorCode.ALBUM_002, 400, "Storage quota exceeded.")

                # Increment storage
                await conn.execute(
                    "UPDATE users SET storage_used_bytes = storage_used_bytes + $1 WHERE id = $2",
                    upload_size,
                    user_uuid,
                )

                row = await album_repo.insert_photo(
                    conn,
                    photo_id,
                    album_uuid,
                    user_uuid,
                    storage_key,
                    filename,
                    upload_size,
                    content_type,
                    is_zip=True,
                )
    except AppError:
        raise
    except Exception:
        # DB failed after MinIO upload succeeded — clean up orphaned file
        logger.error(
            "DB insert failed after ZIP upload, cleaning up MinIO file",
            extra={"album_id": album_id, "key": storage_key},
            exc_info=True,
        )
        try:
            from app.core.async_storage import delete_file

            await delete_file(storage_key)
        except Exception:
            logger.error(
                "Failed to clean up orphaned ZIP file from MinIO",
                extra={"key": storage_key},
                exc_info=True,
            )
        raise AppError(ErrorCode.SYS_500, 500, "Failed to save ZIP. Please try again.")

    logger.info(
        "Album ZIP uploaded",
        extra={"album_id": album_id, "photo_id": str(photo_id), "size": upload_size},
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

        # 1. Delete DB record first (authoritative state)
        deleted = await album_repo.delete_photo(conn, photo_uuid)

    # 2. Best-effort cleanup of storage and quota refund (outside connection scope)
    if deleted:
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
            try:
                await user_repo.decrement_storage_used(uploaded_by, file_size)
            except Exception:
                logger.warning(
                    "Failed to refund storage quota after photo deletion",
                    extra={"photo_id": photo_id, "file_size": file_size},
                    exc_info=True,
                )

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
