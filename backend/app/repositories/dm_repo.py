"""Direct-message repository — conversations & messages (raw SQL)."""

import uuid

from app.core.database import get_pool


async def find_or_create_conversation(user_a: uuid.UUID, user_b: uuid.UUID) -> dict:
    """Sort UUIDs to satisfy CHECK constraint, INSERT ON CONFLICT DO NOTHING, then SELECT.

    Returns conversation dict with id, participant_a, participant_b,
    total_chars, created_at, updated_at.
    """
    low, high = sorted([user_a, user_b])
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO conversations (participant_a, participant_b)
            VALUES ($1, $2)
            ON CONFLICT ON CONSTRAINT uq_conversation_pair DO NOTHING
            """,
            low,
            high,
        )
        row = await conn.fetchrow(
            """
            SELECT id, participant_a, participant_b, total_chars, created_at, updated_at
            FROM conversations
            WHERE participant_a = $1 AND participant_b = $2
            """,
            low,
            high,
        )
        return dict(row)


async def find_conversation_by_id(conversation_id: uuid.UUID, user_id: uuid.UUID) -> dict | None:
    """Find conversation by ID, verify user is a participant.

    Returns None if not found or not participant.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, participant_a, participant_b, total_chars, created_at, updated_at
            FROM conversations
            WHERE id = $1 AND (participant_a = $2 OR participant_b = $2)
            """,
            conversation_id,
            user_id,
        )
        return dict(row) if row else None


async def find_conversations(
    user_id: uuid.UUID, page_size: int = 30, offset: int = 0
) -> tuple[list[dict], int]:
    """List conversations for a user, ordered by updated_at DESC.

    Each row includes conversation fields, other user info, last message,
    and unread count.  Uses COUNT(*) OVER() for total.
    Returns (rows, total).
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT c.id,
                   c.participant_a,
                   c.participant_b,
                   c.total_chars,
                   c.updated_at,
                   -- other user info
                   CASE WHEN c.participant_a = $1 THEN c.participant_b
                        ELSE c.participant_a END AS other_user_id,
                   u.display_name AS other_display_name,
                   u.avatar_url   AS other_avatar_url,
                   -- last message (lateral join)
                   lm.id          AS last_msg_id,
                   lm.conversation_id AS last_msg_conversation_id,
                   lm.sender_id   AS last_msg_sender_id,
                   lm.content     AS last_msg_content,
                   lm.attachment_key  AS last_msg_attachment_key,
                   lm.attachment_name AS last_msg_attachment_name,
                   lm.attachment_size AS last_msg_attachment_size,
                   lm.attachment_expires_at AS last_msg_attachment_expires_at,
                   lm.is_recalled AS last_msg_is_recalled,
                   lm.is_edited   AS last_msg_is_edited,
                   lm.read_at     AS last_msg_read_at,
                   lm.created_at  AS last_msg_created_at,
                   lm.updated_at  AS last_msg_updated_at,
                   lm_u.display_name AS last_msg_sender_display_name,
                   lm_u.avatar_url   AS last_msg_sender_avatar_url,
                   -- unread count
                   (SELECT COUNT(*)
                    FROM dm_messages um
                    WHERE um.conversation_id = c.id
                      AND um.sender_id != $1
                      AND um.read_at IS NULL
                      AND NOT um.is_recalled
                   ) AS unread_count,
                   COUNT(*) OVER() AS _total
            FROM conversations c
            JOIN users u ON u.id = CASE WHEN c.participant_a = $1
                                        THEN c.participant_b
                                        ELSE c.participant_a END
            LEFT JOIN LATERAL (
                SELECT *
                FROM dm_messages dm
                WHERE dm.conversation_id = c.id
                  AND NOT dm.is_recalled
                ORDER BY dm.created_at DESC
                LIMIT 1
            ) lm ON TRUE
            LEFT JOIN users lm_u ON lm_u.id = lm.sender_id
            WHERE c.participant_a = $1 OR c.participant_b = $1
            ORDER BY c.updated_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id,
            page_size,
            offset,
        )

        if rows:
            total = rows[0]["_total"]
            result = [{k: v for k, v in dict(r).items() if k != "_total"} for r in rows]
        else:
            total = await conn.fetchval(
                """
                SELECT COUNT(*) FROM conversations
                WHERE participant_a = $1 OR participant_b = $1
                """,
                user_id,
            )
            result = []

        return result, total


async def insert_message(
    msg_id: uuid.UUID,
    conversation_id: uuid.UUID,
    sender_id: uuid.UUID,
    content: str | None,
    attachment_key: str | None = None,
    attachment_name: str | None = None,
    attachment_size: int | None = None,
    attachment_expires_at: object = None,
) -> dict:
    """Insert a message and bump conversation updated_at.

    Returns message dict with sender info (JOIN users for display_name, avatar_url).
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                WITH inserted AS (
                    INSERT INTO dm_messages
                        (id, conversation_id, sender_id, content,
                         attachment_key, attachment_name, attachment_size,
                         attachment_expires_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING *
                )
                SELECT i.*,
                       u.display_name AS sender_display_name,
                       u.avatar_url   AS sender_avatar_url
                FROM inserted i
                JOIN users u ON i.sender_id = u.id
                """,
                msg_id,
                conversation_id,
                sender_id,
                content,
                attachment_key,
                attachment_name,
                attachment_size,
                attachment_expires_at,
            )
            await conn.execute(
                "UPDATE conversations SET updated_at = NOW() WHERE id = $1",
                conversation_id,
            )
        return dict(row)


async def find_messages(
    conversation_id: uuid.UUID,
    page_size: int = 30,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Paginated messages for a conversation, ordered by created_at DESC.

    JOIN users for sender display_name, avatar_url.
    Uses COUNT(*) OVER() for total.
    Returns (rows, total).
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT m.*,
                   u.display_name AS sender_display_name,
                   u.avatar_url   AS sender_avatar_url,
                   COUNT(*) OVER() AS _total
            FROM dm_messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.conversation_id = $1
            ORDER BY m.created_at DESC
            LIMIT $2 OFFSET $3
            """,
            conversation_id,
            page_size,
            offset,
        )

        if rows:
            total = rows[0]["_total"]
            result = [{k: v for k, v in dict(r).items() if k != "_total"} for r in rows]
        else:
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM dm_messages WHERE conversation_id = $1",
                conversation_id,
            )
            result = []

        return result, total


async def find_message_by_id(message_id: uuid.UUID) -> dict | None:
    """Find a single message by ID. Returns dict or None."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM dm_messages WHERE id = $1",
            message_id,
        )
        return dict(row) if row else None


async def update_message_content(message_id: uuid.UUID, new_content: str) -> dict | None:
    """Update message content, set is_edited = TRUE, updated_at = NOW().

    Returns updated message dict (JOIN users for sender info) or None.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            WITH updated AS (
                UPDATE dm_messages
                SET content = $2, is_edited = TRUE, updated_at = NOW()
                WHERE id = $1
                RETURNING *
            )
            SELECT upd.*,
                   u.display_name AS sender_display_name,
                   u.avatar_url   AS sender_avatar_url
            FROM updated upd
            JOIN users u ON upd.sender_id = u.id
            """,
            message_id,
            new_content,
        )
        return dict(row) if row else None


async def recall_message(message_id: uuid.UUID) -> dict | None:
    """Set is_recalled = TRUE, nullify content and attachment fields.

    Returns updated row or None.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE dm_messages
            SET is_recalled = TRUE,
                content = NULL,
                attachment_key = NULL,
                attachment_name = NULL,
                attachment_size = NULL,
                updated_at = NOW()
            WHERE id = $1
            RETURNING *
            """,
            message_id,
        )
        return dict(row) if row else None


async def mark_messages_read(conversation_id: uuid.UUID, reader_id: uuid.UUID) -> int:
    """Mark all unread, non-recalled messages from the other user as read.

    Returns count of updated rows.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE dm_messages
            SET read_at = NOW()
            WHERE conversation_id = $1
              AND sender_id != $2
              AND read_at IS NULL
              AND NOT is_recalled
            """,
            conversation_id,
            reader_id,
        )
        return int(result.split()[-1]) if result else 0


async def count_total_unread(user_id: uuid.UUID) -> int:
    """Count total unread messages across all conversations where user is participant."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return int(
            await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM dm_messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE (c.participant_a = $1 OR c.participant_b = $1)
                  AND m.sender_id != $1
                  AND m.read_at IS NULL
                  AND NOT m.is_recalled
                """,
                user_id,
            )
        )


async def get_conversation_char_count(conversation_id: uuid.UUID) -> int:
    """Return total_chars from conversations table."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return int(
            await conn.fetchval(
                "SELECT total_chars FROM conversations WHERE id = $1",
                conversation_id,
            )
            or 0
        )


async def increment_char_count(conversation_id: uuid.UUID, delta: int) -> None:
    """Increment (or decrement) the total_chars counter, floored at 0."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE conversations SET total_chars = GREATEST(0, total_chars + $1) WHERE id = $2",
            delta,
            conversation_id,
        )


async def delete_oldest_messages_by_chars(
    conversation_id: uuid.UUID, excess_chars: int
) -> list[dict]:
    """Delete oldest non-recalled messages until *excess_chars* worth of text is removed.

    Returns list of deleted message dicts (attachment_key, attachment_size, sender_id
    needed for cleanup).  Also decrements total_chars accordingly.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(
                """
                WITH ranked AS (
                    SELECT id, content, attachment_key, attachment_size, sender_id,
                           COALESCE(LENGTH(content), 0) AS char_len,
                           SUM(COALESCE(LENGTH(content), 0))
                               OVER (ORDER BY created_at ASC) AS running_total
                    FROM dm_messages
                    WHERE conversation_id = $1
                      AND NOT is_recalled
                    ORDER BY created_at ASC
                ),
                to_delete AS (
                    SELECT id, content, attachment_key, attachment_size, sender_id, char_len
                    FROM ranked
                    WHERE running_total <= $2
                       OR char_len > 0 AND running_total - char_len < $2
                ),
                deleted AS (
                    DELETE FROM dm_messages
                    WHERE id IN (SELECT id FROM to_delete)
                    RETURNING id, content, attachment_key, attachment_size, sender_id
                )
                SELECT *, COALESCE(LENGTH(content), 0) AS char_len FROM deleted
                """,
                conversation_id,
                excess_chars,
            )
            if rows:
                total_removed = sum(r["char_len"] for r in rows)
                await conn.execute(
                    "UPDATE conversations SET total_chars = "
                    "GREATEST(0, total_chars - $1) WHERE id = $2",
                    total_removed,
                    conversation_id,
                )
            return [dict(r) for r in rows]


async def send_message_atomic(
    conversation_id: uuid.UUID,
    msg_id: uuid.UUID,
    sender_id: uuid.UUID,
    content: str | None,
    attachment_key: str | None,
    attachment_name: str | None,
    attachment_size: int | None,
    attachment_expires_at: object,
    content_len: int,
    char_cap: int,
) -> tuple[dict, list[dict]]:
    """Atomically: advisory lock -> enforce char cap -> insert message -> update char count.

    All operations run in a single transaction with pg_advisory_xact_lock
    on the conversation_id to prevent concurrent corruption.

    Returns (inserted_message_row, deleted_messages_for_storage_cleanup).
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # 1. Advisory lock on conversation
            await conn.execute(
                "SELECT pg_advisory_xact_lock(hashtext($1::text))",
                str(conversation_id),
            )

            # 2. Enforce char cap — delete oldest messages if needed
            deleted: list[dict] = []
            if content_len > 0:
                total_chars = (
                    await conn.fetchval(
                        "SELECT total_chars FROM conversations WHERE id = $1",
                        conversation_id,
                    )
                    or 0
                )
                excess = total_chars + content_len - char_cap
                if excess > 0:
                    rows = await conn.fetch(
                        """
                        WITH ranked AS (
                            SELECT id, content, attachment_key, attachment_size, sender_id,
                                   COALESCE(LENGTH(content), 0) AS char_len,
                                   SUM(COALESCE(LENGTH(content), 0))
                                       OVER (ORDER BY created_at ASC) AS running_total
                            FROM dm_messages
                            WHERE conversation_id = $1
                              AND NOT is_recalled
                            ORDER BY created_at ASC
                        ),
                        to_delete AS (
                            SELECT id, content, attachment_key, attachment_size, sender_id, char_len
                            FROM ranked
                            WHERE running_total <= $2
                               OR char_len > 0 AND running_total - char_len < $2
                        ),
                        deleted_rows AS (
                            DELETE FROM dm_messages
                            WHERE id IN (SELECT id FROM to_delete)
                            RETURNING id, content, attachment_key, attachment_size, sender_id
                        )
                        SELECT *, COALESCE(LENGTH(content), 0) AS char_len FROM deleted_rows
                        """,
                        conversation_id,
                        excess,
                    )
                    if rows:
                        total_removed = sum(r["char_len"] for r in rows)
                        await conn.execute(
                            "UPDATE conversations SET total_chars = "
                            "GREATEST(0, total_chars - $1) WHERE id = $2",
                            total_removed,
                            conversation_id,
                        )
                        deleted = [dict(r) for r in rows]

            # 3. Insert message
            row = await conn.fetchrow(
                """
                WITH inserted AS (
                    INSERT INTO dm_messages
                        (id, conversation_id, sender_id, content,
                         attachment_key, attachment_name, attachment_size,
                         attachment_expires_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING *
                )
                SELECT i.*,
                       u.display_name AS sender_display_name,
                       u.avatar_url   AS sender_avatar_url
                FROM inserted i
                JOIN users u ON i.sender_id = u.id
                """,
                msg_id,
                conversation_id,
                sender_id,
                content,
                attachment_key,
                attachment_name,
                attachment_size,
                attachment_expires_at,
            )

            # 4. Bump conversation updated_at
            await conn.execute(
                "UPDATE conversations SET updated_at = NOW() WHERE id = $1",
                conversation_id,
            )

            # 5. Increment char count
            if content_len > 0:
                await conn.execute(
                    "UPDATE conversations SET total_chars = "
                    "GREATEST(0, total_chars + $1) WHERE id = $2",
                    content_len,
                    conversation_id,
                )

            return dict(row), deleted


async def find_expired_file_messages(cutoff: object) -> list[dict]:
    """Find messages with expired attachments that still have an attachment_key."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, conversation_id, attachment_key, attachment_size, sender_id
            FROM dm_messages
            WHERE attachment_expires_at IS NOT NULL
              AND attachment_expires_at < $1
              AND attachment_key IS NOT NULL
            """,
            cutoff,
        )
        return [dict(r) for r in rows]


async def clear_message_attachment(message_id: uuid.UUID) -> None:
    """NULL out all attachment fields on a message."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE dm_messages
            SET attachment_key = NULL,
                attachment_name = NULL,
                attachment_size = NULL,
                attachment_expires_at = NULL
            WHERE id = $1
            """,
            message_id,
        )


async def find_expired_text_messages(cutoff: object) -> list[dict]:
    """Find text-only messages older than cutoff that haven't been recalled."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, conversation_id, content
            FROM dm_messages
            WHERE created_at < $1
              AND NOT is_recalled
              AND attachment_key IS NULL
            """,
            cutoff,
        )
        return [dict(r) for r in rows]


async def delete_messages_by_ids(message_ids: list[uuid.UUID]) -> int:
    """Delete messages by ID list. Returns count of deleted rows."""
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM dm_messages WHERE id = ANY($1::uuid[])",
            message_ids,
        )
        return int(result.split()[-1]) if result else 0


async def get_dm_friends_only(user_id: uuid.UUID) -> bool:
    """Check user_preferences.dm_friends_only for a user. Default FALSE if no row."""
    pool = get_pool()
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            "SELECT dm_friends_only FROM user_preferences WHERE user_id = $1",
            user_id,
        )
        return bool(val) if val is not None else False
