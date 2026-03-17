"""DM service -- direct messaging business logic."""

import io
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
from app.core.errors import AppError, ErrorCode, StorageQuotaError
from app.core.event_bus import emit
from app.repositories import dm_repo


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

    # 4. Check block (bilateral)
    from app.core.database import get_pool
    from app.repositories import social_repo

    pool = get_pool()
    async with pool.acquire() as conn:
        if await social_repo.is_blocked(conn, uuid.UUID(sender_id), uuid.UUID(recipient_id)):
            raise AppError(ErrorCode.DM_001, 403, "Cannot message this user.")

        # 5. Check recipient's dm_friends_only preference
        dm_friends_only = await dm_repo.get_dm_friends_only(uuid.UUID(recipient_id))
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

    if file_data and file_name and file_size:
        if file_size > DM_MAX_ATTACHMENT_SIZE:
            raise AppError(ErrorCode.SYS_422, 422, "File too large (max 50 MB).")

        # Check storage quota
        from app.repositories import user_repo

        used = await user_repo.get_storage_used(uuid.UUID(sender_id))
        if used + file_size > 1_073_741_824:  # 1 GB
            raise StorageQuotaError("Storage quota exceeded (1 GB limit).")

        # Upload to MinIO
        from app.core.storage import upload_file

        storage_key = f"dm/{sender_id}/{uuid.uuid4()}_{file_name}"
        upload_file(file_data, storage_key, file_content_type or "application/octet-stream")

        # Increment storage used
        await user_repo.increment_storage_used(uuid.UUID(sender_id), file_size)

        attachment_key = storage_key
        attachment_name = file_name
        attachment_size = file_size
        attachment_expires_at = datetime.now(timezone.utc) + timedelta(days=DM_FILE_EXPIRY_DAYS)

    # 7. Find or create conversation
    conversation = await dm_repo.find_or_create_conversation(
        uuid.UUID(sender_id), uuid.UUID(recipient_id)
    )
    conversation_id = conversation["id"]

    # 8. Enforce char cap
    content_len = len(content) if content else 0
    if content_len > 0:
        total_chars = await dm_repo.get_conversation_char_count(conversation_id)
        excess = total_chars + content_len - DM_CHAR_CAP_PER_CONVERSATION
        if excess > 0:
            deleted_msgs = await dm_repo.delete_oldest_messages_by_chars(
                conversation_id, excess
            )
            # Refund storage for any deleted attachments
            if deleted_msgs:
                from app.repositories import user_repo

                for dmsg in deleted_msgs:
                    if dmsg.get("attachment_size") and dmsg.get("sender_id"):
                        try:
                            from app.core.storage import delete_file

                            if dmsg.get("attachment_key"):
                                delete_file(dmsg["attachment_key"])
                            await user_repo.decrement_storage_used(
                                dmsg["sender_id"], dmsg["attachment_size"]
                            )
                        except Exception:
                            logger.warning(
                                "Failed to clean up attachment during char cap enforcement",
                                exc_info=True,
                                extra={"msg_id": str(dmsg.get("id"))},
                            )

    # 9. Insert message
    msg_id = uuid.uuid4()
    row = await dm_repo.insert_message(
        msg_id=msg_id,
        conversation_id=conversation_id,
        sender_id=uuid.UUID(sender_id),
        content=content,
        attachment_key=attachment_key,
        attachment_name=attachment_name,
        attachment_size=attachment_size,
        attachment_expires_at=attachment_expires_at,
    )

    # 10. Increment char count
    if content_len > 0:
        await dm_repo.increment_char_count(conversation_id, content_len)

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
    # 1. Find message and verify sender
    row = await dm_repo.find_message_by_id(uuid.UUID(message_id))
    if not row:
        raise AppError(ErrorCode.SYS_404, 404, "Message not found.")
    if str(row["sender_id"]) != sender_id:
        raise AppError(ErrorCode.SYS_403, 403, "Cannot edit another user's message.")

    # 2. Verify not recalled
    if row.get("is_recalled"):
        raise AppError(ErrorCode.SYS_422, 422, "Cannot edit a recalled message.")

    # 3. Verify within edit window
    created_at = row["created_at"]
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=DM_EDIT_RECALL_WINDOW_HOURS)
    if created_at < cutoff:
        raise AppError(ErrorCode.DM_002, 403, "Edit window has expired.")

    # 4. Validate new content length
    if len(new_content) > DM_MAX_MESSAGE_LENGTH:
        raise AppError(
            ErrorCode.SYS_422,
            422,
            f"Message too long (max {DM_MAX_MESSAGE_LENGTH} chars).",
        )

    # 5. Calculate char delta
    old_content = row.get("content") or ""
    char_delta = len(new_content) - len(old_content)

    # 6. Update message content
    updated_row = await dm_repo.update_message_content(uuid.UUID(message_id), new_content)
    if not updated_row:
        raise AppError(ErrorCode.SYS_404, 404, "Message not found.")

    # 7. Update char count
    conversation_id = row["conversation_id"]
    if char_delta != 0:
        await dm_repo.increment_char_count(conversation_id, char_delta)

    # 8. Convert and generate presigned URL
    msg = await async_row_to_message(updated_row)
    if updated_row.get("attachment_key") and not msg.get("is_recalled"):
        from app.core.storage import generate_presigned_url

        msg["attachment_url"] = generate_presigned_url(
            updated_row["attachment_key"],
            expires_in=PRESIGNED_URL_FILE_SECONDS,
            filename=updated_row.get("attachment_name"),
        )

    # 9. Find recipient
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
    # 1. Find message and verify sender
    row = await dm_repo.find_message_by_id(uuid.UUID(message_id))
    if not row:
        raise AppError(ErrorCode.SYS_404, 404, "Message not found.")
    if str(row["sender_id"]) != sender_id:
        raise AppError(ErrorCode.SYS_403, 403, "Cannot recall another user's message.")

    # 2. Verify not already recalled
    if row.get("is_recalled"):
        raise AppError(ErrorCode.SYS_422, 422, "Message already recalled.")

    # 3. Verify within recall window
    created_at = row["created_at"]
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=DM_EDIT_RECALL_WINDOW_HOURS)
    if created_at < cutoff:
        raise AppError(ErrorCode.DM_002, 403, "Recall window has expired.")

    # 4. If has attachment: delete from MinIO and refund storage quota
    if row.get("attachment_key"):
        try:
            from app.core.storage import delete_file

            delete_file(row["attachment_key"])
        except Exception:
            logger.warning(
                "Failed to delete DM attachment from storage",
                exc_info=True,
                extra={"msg_id": message_id},
            )

        if row.get("attachment_size"):
            try:
                from app.repositories import user_repo

                await user_repo.decrement_storage_used(
                    uuid.UUID(sender_id), row["attachment_size"]
                )
            except Exception:
                logger.warning(
                    "Failed to refund storage quota for recalled DM attachment",
                    exc_info=True,
                    extra={"msg_id": message_id},
                )

    # 5. Subtract content length from char count
    conversation_id = row["conversation_id"]
    content_len = len(row.get("content") or "")
    if content_len > 0:
        await dm_repo.increment_char_count(conversation_id, -content_len)

    # 6. Recall message in DB
    recalled_row = await dm_repo.recall_message(uuid.UUID(message_id))
    if not recalled_row:
        raise AppError(ErrorCode.SYS_404, 404, "Message not found.")

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
    rows, total = await dm_repo.find_conversations(
        uuid.UUID(user_id), page_size, offset
    )

    conversations = []
    for row in rows:
        conv = await async_row_to_conversation(row, user_id)
        # Generate presigned URL for last message attachment if present
        last_msg = conv.get("last_message")
        if (
            last_msg
            and last_msg.get("attachment_key")
            and not last_msg.get("is_recalled")
        ):
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
    conv = await dm_repo.find_conversation_by_id(
        uuid.UUID(conversation_id), uuid.UUID(user_id)
    )
    if not conv:
        raise AppError(ErrorCode.SYS_404, 404, "Conversation not found.")

    offset = (page - 1) * page_size
    rows, total = await dm_repo.find_messages(
        uuid.UUID(conversation_id), page_size, offset
    )

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
    conv = await dm_repo.find_conversation_by_id(
        uuid.UUID(conversation_id), uuid.UUID(user_id)
    )
    if not conv:
        raise AppError(ErrorCode.SYS_404, 404, "Conversation not found.")

    count = await dm_repo.mark_messages_read(uuid.UUID(conversation_id), uuid.UUID(user_id))
    if count == 0:
        return None

    read_at = datetime.now(timezone.utc).isoformat()

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
