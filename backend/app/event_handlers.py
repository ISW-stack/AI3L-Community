"""Event handler registration — composition root for the event bus."""

import asyncio
import uuid
from typing import Any

from loguru import logger

from app.core.event_bus import on


async def _is_blocked(user_a: str, user_b: str) -> bool:
    """Check if user_a has user_b in their block set (bilateral)."""
    try:
        from app.core.blacklist import get_blocked_user_ids
        from app.core.database import get_pool
        from app.core.redis import get_redis

        redis = get_redis()
        pool = get_pool()
        blocked = await get_blocked_user_ids(redis, user_a, pool=pool)
        return user_b in blocked
    except Exception:
        return False  # Redis failure → allow notification


async def _check_idempotent(
    user_id: str, entity_type: str | None, entity_id: str | None, action: str
) -> bool:
    """Return True if this notification should be sent (not a duplicate).

    Uses Redis NX with 5-minute TTL to deduplicate.
    """
    try:
        from app.core.redis import get_redis

        redis = get_redis()
        key = f"notify:idempotent:{user_id}:{entity_type}:{entity_id}:{action}"
        result = await redis.set(key, "1", ex=300, nx=True)
        return result is not None  # None means key existed → duplicate
    except Exception:
        # Redis failure → allow notification through (prefer delivery over dedup)
        return True


async def _on_comment_created(
    user_id: str,
    commenter_name: str,
    mention_targets: list[tuple[str, str]],
    reply_target: tuple[str, str] | None,
    post_owner_id: str | None = None,
    post_id: str | None = None,
    **_kwargs: Any,
) -> None:
    from app.services.notification import create_notification

    succeeded = 0
    failed = 0

    # Collect UIDs already notified via mention/reply to avoid duplicate post-owner notification
    notified_uids: set[str] = set()

    for target_uid, pid in mention_targets:
        if await _is_blocked(target_uid, user_id):
            continue  # Skip notification for blocked users
        if not await _check_idempotent(target_uid, "post", pid, "MENTION"):
            continue
        try:
            await create_notification(
                user_id=target_uid,
                trigger_user_id=user_id,
                action_type="MENTION",
                entity_type="post",
                entity_id=pid,
                message=f"{commenter_name} mentioned you in a comment",
            )
            succeeded += 1
            notified_uids.add(target_uid)
        except (ConnectionError, OSError, TimeoutError) as e:
            failed += 1
            logger.warning(
                "Transient error sending mention notification (retryable)",
                extra={"target_uid": target_uid, "error": str(e)},
            )
        except Exception:
            failed += 1
            logger.error("Failed to send mention notification", exc_info=True)

    if reply_target:
        if await _is_blocked(reply_target[0], user_id):
            pass  # Skip notification for blocked users
        elif not await _check_idempotent(reply_target[0], "post", reply_target[1], "REPLY"):
            pass
        else:
            try:
                await create_notification(
                    user_id=reply_target[0],
                    trigger_user_id=user_id,
                    action_type="REPLY",
                    entity_type="post",
                    entity_id=reply_target[1],
                    message=f"{commenter_name} replied to your comment",
                )
                succeeded += 1
                notified_uids.add(reply_target[0])
            except (ConnectionError, OSError, TimeoutError) as e:
                failed += 1
                logger.warning(
                    "Transient error sending reply notification (retryable)",
                    extra={"target_uid": reply_target[0], "error": str(e)},
                )
            except Exception:
                failed += 1
                logger.error("Failed to send reply notification", exc_info=True)

    # Notify post owner about new comment (unless they are the commenter or already notified)
    if (
        post_owner_id
        and post_owner_id != user_id
        and post_owner_id not in notified_uids
        and post_id
    ):
        if not await _is_blocked(post_owner_id, user_id):
            if await _check_idempotent(post_owner_id, "post", post_id, "NEW_COMMENT"):
                try:
                    await create_notification(
                        user_id=post_owner_id,
                        trigger_user_id=user_id,
                        action_type="NEW_COMMENT",
                        entity_type="post",
                        entity_id=post_id,
                        message=f"{commenter_name} commented on your post",
                    )
                    succeeded += 1
                except (ConnectionError, OSError, TimeoutError) as e:
                    failed += 1
                    logger.warning(
                        "Transient error sending post owner comment notification (retryable)",
                        extra={"target_uid": post_owner_id, "error": str(e)},
                    )
                except Exception:
                    failed += 1
                    logger.error(
                        "Failed to send post owner comment notification", exc_info=True
                    )

    if failed:
        logger.error(
            "comment.created notifications summary",
            extra={"succeeded": succeeded, "failed": failed},
        )


async def _on_post_deleted(
    post_owner_id: str,
    admin_user_id: str,
    post_id: str,
    **_kwargs: Any,
) -> None:
    from app.services.notification import create_notification

    if not await _check_idempotent(post_owner_id, "post", post_id, "SYSTEM"):
        return
    try:
        await create_notification(
            user_id=post_owner_id,
            trigger_user_id=admin_user_id,
            action_type="SYSTEM",
            entity_type="post",
            entity_id=post_id,
            message="Your post was removed by an administrator",
        )
    except Exception:
        logger.error("Failed to send post deletion notification", exc_info=True)
        raise  # Let event bus retry


async def _on_application_reviewed(
    applicant_uid: str,
    reviewer_uid: str,
    action: str,
    **_kwargs: Any,
) -> None:
    from app.services.notification import create_notification

    if not await _check_idempotent(applicant_uid, None, None, action):
        return
    msg = (
        "Your membership application was approved"
        if action == "APPROVED"
        else "Your membership application was rejected"
    )
    try:
        await create_notification(
            user_id=applicant_uid,
            trigger_user_id=reviewer_uid,
            action_type="SYSTEM",
            entity_type=None,
            entity_id=None,
            message=msg,
        )
    except Exception:
        logger.error("Failed to send application review notification", exc_info=True)
        raise  # Let event bus retry


async def _on_user_banned(user_id: str, **_kwargs: Any) -> None:
    try:
        from app.api.v1.endpoints.ws import force_logout

        await force_logout(user_id)
    except Exception:
        logger.error("Failed to force logout banned user", exc_info=True)
        raise  # Let event bus retry


async def _on_notification_created(user_id: str, notification: dict, **_kwargs: Any) -> None:
    try:
        from app.api.v1.endpoints.ws import send_to_user

        await send_to_user(
            user_id,
            {
                "type": "NEW_NOTIFICATION",
                "notification": notification,
            },
        )
    except Exception:
        logger.error("Failed to push notification via WebSocket", exc_info=True)
        raise  # Let event bus retry


async def _on_user_role_changed(user_id: str, new_role: str, **_kwargs: Any) -> None:
    """Send a WebSocket notification when a user's role is changed."""
    try:
        from app.api.v1.endpoints.ws import send_to_user

        await send_to_user(user_id, {"type": "ROLE_CHANGED", "new_role": new_role})
    except Exception:
        logger.error("Failed to send role change via WebSocket", exc_info=True)
        raise  # Let event bus retry


async def _on_sig_role_changed(user_id: str, sig_id: str, new_role: str, **_kwargs: Any) -> None:
    """Notify the affected user when their SIG membership role is changed."""
    try:
        from app.api.v1.endpoints.ws import send_to_user

        await send_to_user(
            user_id,
            {"type": "SIG_ROLE_CHANGED", "sig_id": sig_id, "new_role": new_role},
        )
    except Exception:
        logger.error(
            "Failed to send SIG role change via WebSocket",
            extra={"user_id": user_id, "sig_id": sig_id},
            exc_info=True,
        )
        raise  # Let event bus retry


_SIG_MEMBER_BATCH_SIZE = 200
_SIG_NOTIFICATION_MAX = 500
_SIG_NOTIFICATION_CONCURRENCY = 20


async def _on_post_created_in_sig(
    sig_id: str,
    post_id: str,
    author_id: str,
    post_title: str,
    **_kwargs: Any,
) -> None:
    """Notify all SIG members (except the author) about a new post.

    Uses asyncio.Semaphore to limit concurrency and a hard cap to prevent
    blocking the event bus for very large SIGs.
    """
    from app.repositories import sig_repo
    from app.services.notification import create_notification
    from app.services.user import get_user_by_id

    author = await get_user_by_id(uuid.UUID(author_id))
    author_name = author["display_name"] if author else "Someone"

    sem = asyncio.Semaphore(_SIG_NOTIFICATION_CONCURRENCY)
    succeeded = 0
    failed = 0
    notified_count = 0
    cap_reached = False

    async def _notify_member(target_uid: str) -> bool:
        """Send a notification to a single member. Returns True on success."""
        async with sem:
            if await _is_blocked(target_uid, author_id):
                return True  # blocked, skip silently
            if not await _check_idempotent(target_uid, "post", post_id, "SIG_NEW_POST"):
                return True  # deduplicated, not a failure
            try:
                await create_notification(
                    user_id=target_uid,
                    trigger_user_id=author_id,
                    action_type="SIG_NEW_POST",
                    entity_type="post",
                    entity_id=post_id,
                    message=f'{author_name} posted "{post_title[:50]}" in your SIG',
                )
                return True
            except (ConnectionError, OSError, TimeoutError) as e:
                logger.warning(
                    "Transient error sending SIG new post notification (retryable)",
                    extra={"target_uid": target_uid, "error": str(e)},
                )
                return False
            except Exception:
                logger.error("Failed to send SIG new post notification", exc_info=True)
                return False

    offset = 0
    while True:
        members, _total = await sig_repo.find_members(
            uuid.UUID(sig_id), offset=offset, limit=_SIG_MEMBER_BATCH_SIZE
        )
        if not members:
            break

        tasks: list[asyncio.Task[bool]] = []
        for m in members:
            target_uid = str(m["user_id"])
            if target_uid == author_id:
                continue
            notified_count += 1
            if notified_count > _SIG_NOTIFICATION_MAX:
                cap_reached = True
                break
            tasks.append(asyncio.create_task(_notify_member(target_uid)))

        if tasks:
            results = await asyncio.gather(*tasks)
            for ok in results:
                if ok:
                    succeeded += 1
                else:
                    failed += 1

        if cap_reached:
            logger.warning(
                "SIG notification cap reached",
                extra={"sig_id": sig_id, "cap": _SIG_NOTIFICATION_MAX},
            )
            break

        # Stop when the batch is smaller than page size (last page)
        if len(members) < _SIG_MEMBER_BATCH_SIZE:
            break

        offset += _SIG_MEMBER_BATCH_SIZE

    if failed:
        logger.error(
            "post.created_in_sig notifications summary",
            extra={"succeeded": succeeded, "failed": failed},
        )


async def _on_audit_action(
    user_id: str,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    ip_address: str | None = None,
    **_kwargs: Any,
) -> None:
    from app.services.audit import log_action

    await log_action(user_id, action, target_type, target_id, ip_address)


async def _on_co_author_invited(
    post_id: str,
    target_user_id: str,
    inviter_id: str | None = None,
    inviter_name: str = "Someone",
    post_title: str = "",
    **_kwargs: Any,
) -> None:
    """Notify user when invited as co-author."""
    from app.services.notification import create_notification

    # Skip notification if the inviter is the target (shouldn't happen, but be safe)
    if inviter_id and inviter_id == target_user_id:
        return
    if not await _check_idempotent(target_user_id, "post", post_id, "CO_AUTHOR_INVITE"):
        return
    try:
        await create_notification(
            user_id=target_user_id,
            trigger_user_id=inviter_id,
            action_type="CO_AUTHOR_INVITE",
            entity_type="post",
            entity_id=post_id,
            message=f'{inviter_name} invited you as co-author on "{post_title[:50]}"',
        )
    except Exception:
        logger.error("Failed to send co-author invitation notification", exc_info=True)
        raise


async def _on_co_author_responded(
    post_id: str,
    post_owner_id: str,
    responder_id: str | None = None,
    responder_name: str = "Someone",
    accepted: bool = False,
    **_kwargs: Any,
) -> None:
    """Notify post owner when co-author responds to invitation."""
    from app.services.notification import create_notification

    # Skip notification if the responder is the post owner (own action)
    if responder_id and responder_id == post_owner_id:
        return
    action_label = "accepted" if accepted else "rejected"
    if not await _check_idempotent(post_owner_id, "post", post_id, "CO_AUTHOR_RESPONSE"):
        return
    try:
        await create_notification(
            user_id=post_owner_id,
            trigger_user_id=responder_id,
            action_type="CO_AUTHOR_RESPONSE",
            entity_type="post",
            entity_id=post_id,
            message=f"{responder_name} {action_label} your co-author invitation",
        )
    except Exception:
        logger.error("Failed to send co-author response notification", exc_info=True)
        raise


async def _on_post_cited(
    cited_post_id: str,
    citing_post_id: str,
    citer_id: str | None = None,
    citer_name: str = "Someone",
    citing_post_title: str = "",
    **_kwargs: Any,
) -> None:
    """Notify cited post author when their post is cited."""
    from app.repositories import post_repo
    from app.services.notification import create_notification

    # Get the cited post owner
    owner_id = await post_repo.find_owner_id(uuid.UUID(cited_post_id))
    if not owner_id:
        return
    # Skip notification if the citer is the cited post owner (self-action)
    if citer_id and citer_id == owner_id:
        return
    # Use citer_id from event data if available, otherwise look up from DB
    effective_citer_id = citer_id
    if not effective_citer_id:
        effective_citer_id = await post_repo.find_owner_id(uuid.UUID(citing_post_id))
    if effective_citer_id and await _is_blocked(owner_id, effective_citer_id):
        return  # Skip notification for blocked users
    if not await _check_idempotent(owner_id, "post", citing_post_id, "POST_CITED"):
        return
    try:
        await create_notification(
            user_id=owner_id,
            trigger_user_id=citer_id,
            action_type="POST_CITED",
            entity_type="post",
            entity_id=cited_post_id,
            message=f'{citer_name} cited your post in "{citing_post_title[:50]}"',
        )
    except Exception:
        logger.error("Failed to send post citation notification", exc_info=True)
        raise


_QA_INVITE_MAX = 5


async def _on_question_created(
    post_id: str,
    author_id: str,
    keywords: list[str],
    **_kwargs: Any,
) -> None:
    """Notify expert users when a question is posted matching their interests."""
    if not keywords:
        return

    from app.core.redis import get_redis
    from app.services.notification import create_notification

    redis = get_redis()

    from app.core.database import get_pool

    pool = get_pool()
    async with pool.acquire() as conn:
        # Find users with overlapping keywords in their posts (excluding the question author)
        rows = await conn.fetch(
            """
            SELECT DISTINCT p.user_id, u.display_name
            FROM posts p
            JOIN users u ON p.user_id = u.id
            WHERE p.keywords && $1
              AND p.user_id != $2
              AND p.is_deleted = false
              AND u.is_deleted = false
              AND u.is_banned = false
            ORDER BY u.display_name
            LIMIT $3
            """,
            keywords,
            uuid.UUID(author_id),
            _QA_INVITE_MAX,
        )

    for row in rows:
        target_uid = str(row["user_id"])
        if await _is_blocked(target_uid, author_id):
            continue  # Skip notification for blocked users
        dedup_key = f"qa_invite:{post_id}:{target_uid}"
        is_new = await redis.set(dedup_key, "1", ex=86400, nx=True)
        if not is_new:
            continue
        try:
            await create_notification(
                user_id=target_uid,
                trigger_user_id=author_id,
                action_type="QA_INVITE",
                entity_type="post",
                entity_id=post_id,
                message="A new question was posted that matches your expertise",
            )
        except Exception:
            logger.error(
                "Failed to send QA invite notification",
                exc_info=True,
                extra={"target_uid": target_uid, "post_id": post_id},
            )


async def _on_best_answer_marked(
    post_id: str,
    answer_author_id: str,
    question_title: str,
    marker_name: str,
    **_kwargs: Any,
) -> None:
    """Notify the answer author when their answer is marked as best."""
    from app.services.notification import create_notification

    if not await _check_idempotent(answer_author_id, "post", post_id, "BEST_ANSWER_MARKED"):
        return
    try:
        await create_notification(
            user_id=answer_author_id,
            trigger_user_id=None,
            action_type="BEST_ANSWER_MARKED",
            entity_type="post",
            entity_id=post_id,
            message=f'{marker_name} marked your answer as best on "{question_title[:50]}"',
        )
    except Exception:
        logger.error("Failed to send best answer notification", exc_info=True)
        raise


async def _on_friend_request(
    user_id: str,
    target_id: str,
    friendship_id: str,
    **_kwargs: Any,
) -> None:
    """Notify the target user when they receive a friend request."""
    from app.services.notification import create_notification

    if await _is_blocked(target_id, user_id):
        return
    if not await _check_idempotent(target_id, "friendship", friendship_id, "FRIEND_REQUEST"):
        return
    try:
        await create_notification(
            user_id=target_id,
            trigger_user_id=user_id,
            action_type="FRIEND_REQUEST",
            entity_type="friendship",
            entity_id=friendship_id,
            message="You have a new friend request",
        )
    except Exception:
        logger.error("Failed to send friend request notification", exc_info=True)
        raise


async def _on_friend_accepted(
    user_id: str,
    friend_id: str,
    friendship_id: str,
    **_kwargs: Any,
) -> None:
    """Notify the original requester when their friend request is accepted."""
    from app.services.notification import create_notification

    if await _is_blocked(user_id, friend_id):
        return
    if not await _check_idempotent(user_id, "friendship", friendship_id, "FRIEND_ACCEPTED"):
        return
    try:
        await create_notification(
            user_id=user_id,
            trigger_user_id=friend_id,
            action_type="FRIEND_ACCEPTED",
            entity_type="friendship",
            entity_id=friendship_id,
            message="Your friend request was accepted",
        )
    except Exception:
        logger.error("Failed to send friend accepted notification", exc_info=True)
        raise


async def _on_dm_message_sent(recipient_id: str, message: dict, **_kwargs: Any) -> None:
    """Push new DM via WebSocket."""
    try:
        from app.api.v1.endpoints.ws import send_to_user

        await send_to_user(recipient_id, {"type": "NEW_DM", "message": message})
    except Exception:
        logger.error("Failed to push DM via WebSocket", exc_info=True)
        raise


async def _on_dm_message_edited(recipient_id: str, message: dict, **_kwargs: Any) -> None:
    """Push edited DM via WebSocket."""
    try:
        from app.api.v1.endpoints.ws import send_to_user

        await send_to_user(recipient_id, {"type": "DM_EDITED", "message": message})
    except Exception:
        logger.error("Failed to push DM edit via WebSocket", exc_info=True)
        raise


async def _on_dm_message_recalled(
    recipient_id: str, message_id: str, conversation_id: str, **_kwargs: Any
) -> None:
    """Push recalled DM via WebSocket."""
    try:
        from app.api.v1.endpoints.ws import send_to_user

        await send_to_user(
            recipient_id,
            {
                "type": "DM_RECALLED",
                "message_id": message_id,
                "conversation_id": conversation_id,
            },
        )
    except Exception:
        logger.error("Failed to push DM recall via WebSocket", exc_info=True)
        raise


async def _on_dm_messages_read(
    sender_id: str, conversation_id: str, read_at: str, **_kwargs: Any
) -> None:
    """Push read receipt via WebSocket."""
    try:
        from app.api.v1.endpoints.ws import send_to_user

        await send_to_user(
            sender_id,
            {
                "type": "DM_READ",
                "conversation_id": conversation_id,
                "read_at": read_at,
            },
        )
    except Exception:
        logger.error("Failed to push DM read receipt via WebSocket", exc_info=True)
        raise


def register_all() -> None:
    """Register all event handlers. Called once at application startup."""
    on("comment.created", _on_comment_created)
    on("post.deleted", _on_post_deleted)
    on("application.reviewed", _on_application_reviewed)
    on("user.banned", _on_user_banned)
    on("user.role_changed", _on_user_role_changed)
    on("sig.role_changed", _on_sig_role_changed)
    on("notification.created", _on_notification_created)
    on("post.created_in_sig", _on_post_created_in_sig)
    on("audit.action", _on_audit_action)
    on("co_author.invited", _on_co_author_invited)
    on("co_author.responded", _on_co_author_responded)
    on("post.cited", _on_post_cited)
    on("question.created", _on_question_created)
    on("best_answer.marked", _on_best_answer_marked)
    on("friend.request", _on_friend_request)
    on("friend.accepted", _on_friend_accepted)
    on("dm.message_sent", _on_dm_message_sent)
    on("dm.message_edited", _on_dm_message_edited)
    on("dm.message_recalled", _on_dm_message_recalled)
    on("dm.messages_read", _on_dm_messages_read)
