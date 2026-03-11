import uuid

from loguru import logger

from app.converters.report_converter import row_to_report
from app.repositories import report_repo


async def create_report(post_id: uuid.UUID, user_id: str, reason: str) -> dict:
    report_id = uuid.uuid4()
    row = await report_repo.insert(report_id, post_id, uuid.UUID(user_id), reason)
    if row is None:
        raise ValueError("You have already reported this post.")
    logger.info("Report created", extra={"report_id": str(report_id), "post_id": str(post_id)})
    return row_to_report(row)


async def list_reports(
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    offset = (page - 1) * page_size
    rows, total = await report_repo.find_many(status_filter, offset, page_size)
    return [row_to_report(r) for r in rows], total


async def review_report(report_id: uuid.UUID, reviewer_id: str, new_status: str) -> dict | None:
    row = await report_repo.update_status(report_id, uuid.UUID(reviewer_id), new_status)
    if not row:
        return None
    logger.info("Report reviewed", extra={"report_id": str(report_id), "status": new_status})

    # Notify the reporter about the outcome
    reporter_id = row.get("user_id")
    if reporter_id:
        try:
            from app.services.notification import create_notification

            status_text = "resolved" if new_status == "RESOLVED" else "dismissed"
            await create_notification(
                user_id=str(reporter_id),
                trigger_user_id=reviewer_id,
                action_type="report_reviewed",
                entity_type="report",
                entity_id=str(report_id),
                message=f"Your report has been {status_text} by a moderator.",
            )
        except Exception:
            logger.warning(
                "Failed to notify reporter",
                extra={"report_id": str(report_id)},
            )

    return row_to_report(row)
