import uuid

from loguru import logger

from app.core.event_bus import emit
from app.repositories import application_repo


async def create_application(user_id: uuid.UUID, description: str) -> dict:
    app_id = uuid.uuid4()
    row = await application_repo.insert(app_id, user_id, description)
    if row is None:
        raise ValueError("You already have a pending application.")
    logger.info("Membership application created", extra={"user_id": str(user_id)})
    return row


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

    # Notify applicant via event bus
    await emit(
        "application.reviewed",
        applicant_uid=str(result["user_id"]),
        reviewer_uid=str(reviewer_id),
        action=action,
    )

    return result
