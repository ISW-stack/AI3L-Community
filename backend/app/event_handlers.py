"""Event handler registration — composition root for the event bus."""

import uuid
from typing import Any

from loguru import logger

from app.core.event_bus import on


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
    **_kwargs: Any,
) -> None:
    from app.services.notification import create_notification

    succeeded = 0
    failed = 0

    for target_uid, cid in mention_targets:
        if not await _check_idempotent(target_uid, "comment", cid, "MENTION"):
            continue
        try:
            await create_notification(
                user_id=target_uid,
                trigger_user_id=user_id,
                action_type="MENTION",
                entity_type="comment",
                entity_id=cid,
                message=f"{commenter_name} mentioned you in a comment",
            )
            succeeded += 1
        except Exception:
            failed += 1
            logger.error("Failed to send mention notification", exc_info=True)

    if reply_target:
        if not await _check_idempotent(reply_target[0], "comment", reply_target[1], "REPLY"):
            pass
        else:
            try:
                await create_notification(
                    user_id=reply_target[0],
                    trigger_user_id=user_id,
                    action_type="REPLY",
                    entity_type="comment",
                    entity_id=reply_target[1],
                    message=f"{commenter_name} replied to your comment",
                )
                succeeded += 1
            except Exception:
                failed += 1
                logger.error("Failed to send reply notification", exc_info=True)

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


async def _on_user_banned(user_id: str, **_kwargs: Any) -> None:
    try:
        from app.api.v1.endpoints.ws import force_logout

        await force_logout(user_id)
    except Exception:
        logger.error("Failed to force logout banned user", exc_info=True)


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


_SIG_MEMBER_BATCH_SIZE = 200


async def _on_post_created_in_sig(
    sig_id: str,
    post_id: str,
    author_id: str,
    post_title: str,
    **_kwargs: Any,
) -> None:
    """Notify all SIG members (except the author) about a new post."""
    from app.repositories import sig_repo
    from app.services.notification import create_notification
    from app.services.user import get_user_by_id

    author = await get_user_by_id(uuid.UUID(author_id))
    author_name = author["display_name"] if author else "Someone"

    succeeded = 0
    failed = 0
    offset = 0
    while True:
        members, total = await sig_repo.find_members(
            uuid.UUID(sig_id), offset=offset, limit=_SIG_MEMBER_BATCH_SIZE
        )
        if not members:
            break
        for m in members:
            target_uid = str(m["user_id"])
            if target_uid == author_id:
                continue
            if not await _check_idempotent(target_uid, "post", post_id, "SIG_NEW_POST"):
                continue
            try:
                await create_notification(
                    user_id=target_uid,
                    trigger_user_id=author_id,
                    action_type="SIG_NEW_POST",
                    entity_type="post",
                    entity_id=post_id,
                    message=f'{author_name} posted "{post_title[:50]}" in your SIG',
                )
                succeeded += 1
            except Exception:
                failed += 1
                logger.error("Failed to send SIG new post notification", exc_info=True)
        offset += _SIG_MEMBER_BATCH_SIZE
        if offset >= total:
            break

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


def register_all() -> None:
    """Register all event handlers. Called once at application startup."""
    on("comment.created", _on_comment_created)
    on("post.deleted", _on_post_deleted)
    on("application.reviewed", _on_application_reviewed)
    on("user.banned", _on_user_banned)
    on("notification.created", _on_notification_created)
    on("post.created_in_sig", _on_post_created_in_sig)
    on("audit.action", _on_audit_action)
