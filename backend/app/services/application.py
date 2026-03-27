import uuid

import asyncpg
from loguru import logger

from app.core.event_bus import emit
from app.core.security import async_hash_password
from app.repositories import application_repo


async def create_application(
    guest_id: uuid.UUID,
    username: str,
    password: str,
    display_name: str,
    description: str,
) -> dict:
    """Create a user record and membership application atomically.

    The guest's Redis-only UUID becomes a real user row so the FK constraint
    on membership_applications.user_id is satisfied.
    """
    app_id = uuid.uuid4()
    password_hash = await async_hash_password(password)
    try:
        row = await application_repo.insert_with_user(
            app_id, guest_id, username, password_hash, display_name, description
        )
    except asyncpg.UniqueViolationError as exc:
        detail = str(exc).lower()
        if "username" in detail:
            raise ValueError("Username already taken.")
        # Other unique constraint violations (e.g. application PK collision
        # from a concurrent double submit)
        raise ValueError("You have already submitted an application.")
    if row is None:
        raise ValueError("You already have a pending application.")
    logger.info("Membership application created", extra={"user_id": str(guest_id)})

    # Notify all ADMIN / SUPER_ADMIN users about the new application.
    # Failure must not crash the endpoint — the application is already persisted.
    try:
        await emit(
            "application.created",
            applicant_uid=str(guest_id),
            display_name=display_name,
        )
    except Exception:
        logger.error("Failed to emit application.created event", exc_info=True)

    return row


async def get_my_application(user_id: uuid.UUID) -> dict | None:
    """Return the most recent application for a user."""
    return await application_repo.find_latest_by_user(user_id)


async def list_applications(
    status_filter: str | None = None, offset: int = 0, limit: int = 50
) -> tuple[list[dict], int]:
    return await application_repo.find_many(status_filter, offset, limit)


async def review_application(app_id: uuid.UUID, reviewer_id: uuid.UUID, action: str) -> dict | None:
    VALID_ACTIONS = {"APPROVED", "REJECTED"}
    if action not in VALID_ACTIONS:
        raise ValueError(f"Invalid action: must be one of {VALID_ACTIONS}")

    result = await application_repo.update_status(app_id, reviewer_id, action)
    if result is None:
        return None

    if action == "APPROVED":
        logger.info(
            "Membership approved, user promoted",
            extra={"user_id": str(result["user_id"])},
        )
        # Revoke old GUEST sessions so user must re-login with MEMBER role
        from app.services.auth import revoke_user_sessions

        await revoke_user_sessions(str(result["user_id"]))

    # Notify applicant via event bus.
    # Failure must not crash the endpoint — the review is already persisted.
    try:
        await emit(
            "application.reviewed",
            applicant_uid=str(result["user_id"]),
            reviewer_uid=str(reviewer_id),
            action=action,
        )
    except Exception:
        logger.error("Failed to emit application.reviewed event", exc_info=True)

    return result
