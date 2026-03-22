"""DM service -- direct messaging business logic."""

import mimetypes
import uuid
from datetime import datetime, timedelta, timezone

from loguru import logger

from app.converters.dm_converter import async_row_to_conversation, async_row_to_message
from app.core.constants import (
    DM_CHAR_CAP_PER_CONVERSATION,
    DM_EDIT_RECALL_WINDOW_HOURS,
    DM_FILE_EXPIRY_DAYS,
    DM_MAX_ATTACHMENT_SIZE,
    DM_MAX_MESSAGE_LENGTH,
    PRESIGNED_URL_FILE_SECONDS,
)
from app.core.errors import AppError, ErrorCode
from app.core.event_bus import emit
from app.core.file_validation import sanitize_html, validate_magic_number
from app.repositories import dm_repo

# ── DM attachment allowed extensions ────────────────────────────────────────
_DM_ALLOWED_EXTENSIONS: set[str] = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",  # images
    ".pdf",
    ".docx",
    ".xlsx",  # documents
    ".pptx",
    ".txt",
    ".csv",
    ".zip",  # other
}

# Extensions that require magic-byte validation (images)
_DM_MAGIC_CHECK_EXTENSIONS: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".zip": "application/zip",
    ".docx": "application/zip",
    ".xlsx": "application/zip",
    ".pptx": "application/zip",
}

# Magic bytes for types not covered by validate_magic_number
_MAGIC_BYTES: dict[str, list[bytes]] = {
    "application/zip": [b"PK\x03\x04", b"PK\x05\x06"],
}


def _validate_dm_file(file_name: str, file_data: bytes) -> None:
    """Validate DM attachment: extension allowlist + magic bytes for images/PDFs.

    Raises AppError if validation fails.
    """
    ext = ""
    if file_name and "." in file_name:
        ext = "." + file_name.rsplit(".", 1)[-1].lower()

    if ext not in _DM_ALLOWED_EXTENSIONS:
        raise AppError(
            ErrorCode.FILE_001,
            400,
            f"File type not allowed. Accepted: {', '.join(sorted(_DM_ALLOWED_EXTENSIONS))}",
        )

    # For types with known magic signatures, verify content matches extension
    expected_type = _DM_MAGIC_CHECK_EXTENSIONS.get(ext)
    if expected_type:
        # Use inline magic byte check for ZIP types not in validate_magic_number
        magic_patterns = _MAGIC_BYTES.get(expected_type)
        if magic_patterns:
            if not any(file_data.startswith(m) for m in magic_patterns):
                raise AppError(
                    ErrorCode.FILE_001,
                    400,
                    "File content does not match its extension (invalid magic number).",
                )
        elif not validate_magic_number(file_data, expected_type):
            raise AppError(
                ErrorCode.FILE_001,
                400,
                "File content does not match its extension (invalid magic number).",
            )


async def send_message(
    sender_id: str,
    recipient_id: str,
    content: str | None = None,
    file_data: bytes | None = None,
    file_name: str | None = None,
    file_size: int | None = None,
    file_content_type: str | None = None,
) -> dict:
    """Send a DM. Validates permissions, handles attachments, enforces char cap."""
    # 1. Cannot message yourself
    if sender_id == recipient_id:
        raise AppError(ErrorCode.DM_003, 400, "Cannot message yourself.")

    # 2. Must have content or file
    if not content and not file_data:
        raise AppError(ErrorCode.SYS_422, 422, "Message must have content or an attachment.")

    # 3. Validate content length
    if content and len(content) > DM_MAX_MESSAGE_LENGTH:
        raise AppError(
            ErrorCode.SYS_422,
            422,
            f"Message too long (max {DM_MAX_MESSAGE_LENGTH} chars).",
        )

    # B-04/S-01: Sanitize HTML content before storing
    if content:
        content = sanitize_html(content)

    # M-15: Reject if content becomes empty after sanitization
    if content is not None and not content.strip() and not file_data:
        raise AppError(ErrorCode.SYS_422, 422, "Message must have content or an attachment.")

    # 4. Check block (bilateral)
    from app.core.database import get_pool
    from app.repositories import social_repo

    pool = get_pool()
    async with pool.acquire() as conn:
        # Wrap block + friendship checks in a transaction to prevent TOCTOU races
        async with conn.transaction():
            if await social_repo.is_blocked(conn, uuid.UUID(sender_id), uuid.UUID(recipient_id)):
                raise AppError(ErrorCode.DM_001, 403, "Cannot message this user.")

            # 5. Check recipient's dm_friends_only preference (inline query
            # to avoid separate connection in dm_repo.get_dm_friends_only)
            dm_friends_only_val = await conn.fetchval(
                "SELECT dm_friends_only FROM user_preferences WHERE user_id = $1",
                uuid.UUID(recipient_id),
            )
            dm_friends_only = (
                bool(dm_friends_only_val) if dm_friends_only_val is not None else False
            )
            if dm_friends_only:
                friendship = await social_repo.find_friendship_between(
                    conn, uuid.UUID(sender_id), uuid.UUID(recipient_id)
                )
                if not friendship or friendship["status"] != "ACCEPTED":
                    raise AppError(
                        ErrorCode.DM_001,
                        403,
                        "This user only accepts messages from friends.",
                    )

    # 6. Handle file attachment
    attachment_key: str | None = None
    attachment_name: str | None = None
    attachment_size: int | None = None
    attachment_expires_at: datetime | None = None
    quota_reserved = False  # H-03: track whether we pre-reserved storage quota

    if file_data and file_name and file_size:
        if file_size > DM_MAX_ATTACHMENT_SIZE:
            raise AppError(ErrorCode.DM_005, 413, "File too large (max 10 MB).")

        # L-10: Redundant size check on actual data length
        if len(file_data) > DM_MAX_ATTACHMENT_SIZE:
            raise AppError(ErrorCode.DM_005, 413, "File too large (max 10 MB).")

        # S-02: Validate file type before upload
        _validate_dm_file(file_name, file_data)

        # H-03: Atomic check-and-reserve quota in a single UPDATE to prevent TOCTOU race.
        # If later steps fail, the reserved bytes are refunded in the except block.
        pool_quota = get_pool()
        async with pool_quota.acquire() as qconn:
            reserved = await qconn.fetchval(
                """
                UPDATE users
                SET storage_used_bytes = storage_used_bytes + $1
                WHERE id = $2
                  AND COALESCE(storage_used_bytes, 0) + $1 <= 1073741824
                RETURNING storage_used_bytes
                """,
                file_size,
                uuid.UUID(sender_id),
            )
            if reserved is None:
                raise AppError(ErrorCode.DM_004, 413, "Storage quota exceeded (1 GB limit).")
        quota_reserved = True

        # B-27/S-03: Sanitize filename — only preserve extension, not full name
        ext = ""
        if file_name and "." in file_name:
            ext = "." + file_name.rsplit(".", 1)[-1].lower()

        # M-12: Derive Content-Type from extension instead of trusting client
        derived_type = (
            _DM_MAGIC_CHECK_EXTENSIONS.get(ext)
            or mimetypes.guess_type(file_name)[0]
            or "application/octet-stream"
        )

        storage_key = f"dm/{sender_id}/{uuid.uuid4().hex}{ext}"
        attachment_name = file_name
        attachment_size = file_size
        attachment_expires_at = datetime.now(timezone.utc) + timedelta(days=DM_FILE_EXPIRY_DAYS)

    # 7-10. Wrapped in try/except to refund quota + clean up orphaned file on failure
    try:
        # Upload to MinIO inside try so quota is refunded on upload failure
        if file_data and file_name and file_size:
            from app.core.async_storage import upload_file as async_upload_file

            await async_upload_file(file_data, storage_key, derived_type)  # type: ignore
            attachment_key = storage_key  # type: ignore[possibly-undefined]

        # 7. Find or create conversation
        conversation = await dm_repo.find_or_create_conversation(
            uuid.UUID(sender_id), uuid.UUID(recipient_id)
        )
        conversation_id = conversation["id"]

        # 8-10. Atomic: advisory lock + char cap enforcement + insert + char count update
        content_len = len(content) if content else 0
        msg_id = uuid.uuid4()
        row, deleted_msgs = await dm_repo.send_message_atomic(
            conversation_id=conversation_id,
            msg_id=msg_id,
            sender_id=uuid.UUID(sender_id),
            content=content,
            attachment_key=attachment_key,
            attachment_name=attachment_name,
            attachment_size=attachment_size,
            attachment_expires_at=attachment_expires_at,
            content_len=content_len,
            char_cap=DM_CHAR_CAP_PER_CONVERSATION,
        )

        # H-03: Quota was already atomically reserved before upload.
        # No separate increment needed here.

        # Refund storage for any deleted attachments (outside transaction)
        if deleted_msgs:
            from app.repositories import user_repo

            for dmsg in deleted_msgs:
                if dmsg.get("attachment_size") and dmsg.get("sender_id"):
                    try:
                        from app.core.async_storage import delete_file as async_delete_file

                        if dmsg.get("attachment_key"):
                            await async_delete_file(dmsg["attachment_key"])
                        await user_repo.decrement_storage_used(
                            dmsg["sender_id"], dmsg["attachment_size"]
                        )
                    except Exception:
                        logger.warning(
                            "Failed to clean up attachment during char cap enforcement",
                            exc_info=True,
                            extra={"msg_id": str(dmsg.get("id"))},
                        )
    except Exception:
        # H-03: Refund pre-reserved storage quota on failure
        if quota_reserved and file_size:
            try:
                from app.repositories import user_repo

                await user_repo.decrement_storage_used(uuid.UUID(sender_id), file_size)
            except Exception:
                logger.warning(
                    "Failed to refund storage quota after DM send failure",
                    exc_info=True,
                    extra={"sender_id": sender_id, "file_size": file_size},
                )
        # M-48: Clean up orphaned MinIO file if DB operations failed
        if attachment_key:
            try:
                from app.core.async_storage import delete_file as async_delete_file

                await async_delete_file(attachment_key)
            except Exception:
                logger.warning(
                    "Failed to clean up orphaned DM attachment after DB failure",
                    exc_info=True,
                    extra={"storage_key": attachment_key},
                )
        raise

    # 11. Convert row and generate presigned URL if attachment
    msg = await async_row_to_message(row)
    if attachment_key and not msg.get("is_recalled"):
        from app.core.storage import generate_presigned_url

        msg["attachment_url"] = generate_presigned_url(
            attachment_key,
            expires_in=PRESIGNED_URL_FILE_SECONDS,
            filename=attachment_name,
        )

    # 12. Emit event
    await emit(
        "dm.message_sent",
        sender_id=sender_id,
        recipient_id=recipient_id,
        message=msg,
    )

    logger.info(
        "DM sent",
        extra={
            "sender_id": sender_id,
            "recipient_id": recipient_id,
            "conversation_id": str(conversation_id),
            "has_attachment": attachment_key is not None,
        },
    )

    return msg


async def edit_message(message_id: str, sender_id: str, new_content: str) -> dict:
    """Edit a message within the edit window."""
    # Validate new content length upfront (doesn't need DB)
    if len(new_content) > DM_MAX_MESSAGE_LENGTH:
        raise AppError(
            ErrorCode.SYS_422,
            422,
            f"Message too long (max {DM_MAX_MESSAGE_LENGTH} chars).",
        )

    # Sanitize HTML content before storing
    new_content = sanitize_html(new_content)

    from app.core.database import get_pool

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # 1. Find message with lock
            row = await conn.fetchrow(
                "SELECT * FROM dm_messages WHERE id = $1 FOR UPDATE",
                uuid.UUID(message_id),
            )
            if not row:
                raise AppError(ErrorCode.SYS_404, 404, "Message not found.")
            if str(row["sender_id"]) != sender_id:
                raise AppError(ErrorCode.SYS_403, 403, "Cannot edit another user's message.")
            if row.get("is_recalled"):
                raise AppError(ErrorCode.SYS_422, 422, "Cannot edit a recalled message.")

            # 2. Verify within edit window
            created_at = row["created_at"]
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            cutoff = datetime.now(timezone.utc) - timedelta(hours=DM_EDIT_RECALL_WINDOW_HOURS)
            if created_at < cutoff:
                raise AppError(ErrorCode.DM_002, 403, "Edit window has expired.")

            # 3. Advisory lock on conversation
            conversation_id = row["conversation_id"]
            await conn.fetchval(
                "SELECT pg_advisory_xact_lock(hashtext($1::text))",
                str(conversation_id),
            )

            # 4. Calculate char delta from fresh data
            old_content = row.get("content") or ""
            char_delta = len(new_content) - len(old_content)

            # 5. Update message
            updated_row = await conn.fetchrow(
                "UPDATE dm_messages SET content = $1, is_edited = TRUE, updated_at = NOW() "
                "WHERE id = $2 AND is_recalled = false RETURNING *",
                new_content,
                uuid.UUID(message_id),
            )
            if not updated_row:
                raise AppError(ErrorCode.SYS_422, 422, "Cannot edit a recalled message.")
            if char_delta != 0:
                await conn.execute(
                    "UPDATE conversations SET total_chars = GREATEST(0, total_chars + $1) "
                    "WHERE id = $2",
                    char_delta,
                    conversation_id,
                )
            await conn.execute(
                "UPDATE conversations SET updated_at = NOW() WHERE id = $1",
                conversation_id,
            )

    # Convert and generate presigned URL
    msg = await async_row_to_message(updated_row)
    if updated_row.get("attachment_key") and not msg.get("is_recalled"):
        from app.core.storage import generate_presigned_url

        msg["attachment_url"] = generate_presigned_url(
            updated_row["attachment_key"],
            expires_in=PRESIGNED_URL_FILE_SECONDS,
            filename=updated_row.get("attachment_name"),
        )

    # Find recipient
    conv = await dm_repo.find_conversation_by_id(conversation_id, uuid.UUID(sender_id))
    if conv:
        other_id = (
            str(conv["participant_b"])
            if str(conv["participant_a"]) == sender_id
            else str(conv["participant_a"])
        )
        await emit("dm.message_edited", recipient_id=other_id, message=msg)

    return msg


async def recall_message(message_id: str, sender_id: str) -> dict:
    """Recall a message within the recall window."""
    from app.core.database import get_pool

    pool = get_pool()
    attachment_key = None
    attachment_size = None

    async with pool.acquire() as conn:
        async with conn.transaction():
            # 1. Find message with lock
            row = await conn.fetchrow(
                "SELECT * FROM dm_messages WHERE id = $1 FOR UPDATE",
                uuid.UUID(message_id),
            )
            if not row:
                raise AppError(ErrorCode.SYS_404, 404, "Message not found.")
            if str(row["sender_id"]) != sender_id:
                raise AppError(
                    ErrorCode.SYS_403,
                    403,
                    "Cannot recall another user's message.",
                )
            if row.get("is_recalled"):
                raise AppError(ErrorCode.SYS_422, 422, "Message already recalled.")

            # 2. Verify within recall window
            created_at = row["created_at"]
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            cutoff = datetime.now(timezone.utc) - timedelta(hours=DM_EDIT_RECALL_WINDOW_HOURS)
            if created_at < cutoff:
                raise AppError(ErrorCode.DM_002, 403, "Recall window has expired.")

            # 3. Advisory lock on conversation
            conversation_id = row["conversation_id"]
            await conn.fetchval(
                "SELECT pg_advisory_xact_lock(hashtext($1::text))",
                str(conversation_id),
            )

            # 4. Compute content_len from fresh data
            content_len = len(row.get("content") or "")

            # Save attachment info for cleanup after transaction
            attachment_key = row.get("attachment_key")
            attachment_size = row.get("attachment_size")

            # 5. Recall message — also null out attachment fields (M-14 fix)
            recalled_row = await conn.fetchrow(
                "UPDATE dm_messages SET is_recalled = true, content = NULL, "
                "attachment_key = NULL, attachment_name = NULL, "
                "attachment_size = NULL, attachment_expires_at = NULL, "
                "updated_at = NOW() WHERE id = $1 RETURNING *",
                uuid.UUID(message_id),
            )
            if not recalled_row:
                raise AppError(ErrorCode.SYS_404, 404, "Message not found.")
            if content_len > 0:
                await conn.execute(
                    "UPDATE conversations SET total_chars = GREATEST(0, total_chars - $1) "
                    "WHERE id = $2",
                    content_len,
                    conversation_id,
                )
            await conn.execute(
                "UPDATE conversations SET updated_at = NOW() WHERE id = $1",
                conversation_id,
            )

    # 6. If had attachment: delete from MinIO and refund storage (after transaction)
    if attachment_key:
        try:
            from app.core.async_storage import delete_file as async_delete_file

            await async_delete_file(attachment_key)
        except Exception:
            logger.warning(
                "Failed to delete DM attachment from storage",
                exc_info=True,
                extra={"msg_id": message_id},
            )

        if attachment_size:
            try:
                from app.repositories import user_repo

                await user_repo.decrement_storage_used(uuid.UUID(sender_id), attachment_size)
            except Exception:
                logger.warning(
                    "Failed to refund storage quota for recalled DM attachment",
                    exc_info=True,
                    extra={"msg_id": message_id},
                )

    msg = await async_row_to_message(recalled_row)

    # 7. Find recipient and emit event
    conv = await dm_repo.find_conversation_by_id(conversation_id, uuid.UUID(sender_id))
    if conv:
        other_id = (
            str(conv["participant_b"])
            if str(conv["participant_a"]) == sender_id
            else str(conv["participant_a"])
        )
        await emit(
            "dm.message_recalled",
            recipient_id=other_id,
            message_id=message_id,
            conversation_id=str(conversation_id),
        )

    return msg


async def list_conversations(
    user_id: str, page: int = 1, page_size: int = 30
) -> tuple[list[dict], int]:
    """List conversations with presigned URLs for last message attachments."""
    offset = (page - 1) * page_size
    rows, total = await dm_repo.find_conversations(uuid.UUID(user_id), page_size, offset)

    conversations = []
    for row in rows:
        conv = await async_row_to_conversation(row, user_id)
        # Generate presigned URL for last message attachment if present
        last_msg = conv.get("last_message")
        if last_msg and last_msg.get("attachment_key") and not last_msg.get("is_recalled"):
            from app.core.storage import generate_presigned_url

            last_msg["attachment_url"] = generate_presigned_url(
                last_msg["attachment_key"],
                expires_in=PRESIGNED_URL_FILE_SECONDS,
                filename=last_msg.get("attachment_name"),
            )
        conversations.append(conv)

    return conversations, total


async def list_messages(
    user_id: str, conversation_id: str, page: int = 1, page_size: int = 30
) -> tuple[list[dict], int]:
    """List messages, verifying user is participant. Generate presigned URLs."""
    # Verify user is a participant
    conv = await dm_repo.find_conversation_by_id(uuid.UUID(conversation_id), uuid.UUID(user_id))
    if not conv:
        raise AppError(ErrorCode.DM_006, 404, "Conversation not found.")

    offset = (page - 1) * page_size
    rows, total = await dm_repo.find_messages(uuid.UUID(conversation_id), page_size, offset)

    messages = []
    for row in rows:
        msg = await async_row_to_message(row)
        if row.get("attachment_key") and not row.get("is_recalled"):
            from app.core.storage import generate_presigned_url

            msg["attachment_url"] = generate_presigned_url(
                row["attachment_key"],
                expires_in=PRESIGNED_URL_FILE_SECONDS,
                filename=row.get("attachment_name"),
            )
        messages.append(msg)

    return messages, total


async def mark_read(user_id: str, conversation_id: str) -> str | None:
    """Mark all unread messages in conversation as read.

    Returns read_at ISO string or None if nothing to mark.
    """
    # Verify user is a participant
    conv = await dm_repo.find_conversation_by_id(uuid.UUID(conversation_id), uuid.UUID(user_id))
    if not conv:
        raise AppError(ErrorCode.DM_006, 404, "Conversation not found.")

    count, read_at = await dm_repo.mark_messages_read(
        uuid.UUID(conversation_id), uuid.UUID(user_id)
    )
    if count == 0:
        return None

    # Find the other participant to send read receipt
    other_id = (
        str(conv["participant_b"])
        if str(conv["participant_a"]) == user_id
        else str(conv["participant_a"])
    )
    await emit(
        "dm.messages_read",
        sender_id=other_id,
        conversation_id=conversation_id,
        read_at=read_at,
    )

    return read_at


async def get_unread_count(user_id: str) -> int:
    """Get total unread DM count."""
    return await dm_repo.count_total_unread(uuid.UUID(user_id))
