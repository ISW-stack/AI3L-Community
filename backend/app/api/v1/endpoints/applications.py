import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from loguru import logger

from app.core.deps import get_current_user, require_role
from app.core.errors import AppError, ErrorCode
from app.core.event_bus import emit
from app.schemas.application import (
    ApplicationListResponse,
    ApplicationResponse,
    ReviewApplicationRequest,
)
from app.schemas.auth import MessageResponse
from app.schemas.user import ApplyMemberRequest
from app.services.application import create_application, list_applications, review_application

router = APIRouter(tags=["applications"])


def _app_to_response(app: dict) -> ApplicationResponse:
    return ApplicationResponse(
        id=str(app["id"]),
        user_id=str(app["user_id"]),
        username=app.get("username", ""),
        display_name=app.get("display_name", ""),
        description=app["description"],
        status=app["status"],
        reviewed_by=str(app["reviewed_by"]) if app.get("reviewed_by") else None,
        reviewed_at=app["reviewed_at"].isoformat() if app.get("reviewed_at") else None,
        created_at=app["created_at"].isoformat(),
    )


@router.post("/users/apply-member", response_model=MessageResponse)
async def apply_for_membership(
    req: ApplyMemberRequest,
    current_user: dict = Depends(get_current_user),
) -> MessageResponse:
    if current_user["role"] != "GUEST":
        raise AppError(
            ErrorCode.SYS_422,
            status.HTTP_400_BAD_REQUEST,
            "Only guests can apply for membership.",
        )

    try:
        await create_application(uuid.UUID(current_user["sub"]), req.description)
    except ValueError as e:
        raise AppError(ErrorCode.SYS_409, status.HTTP_409_CONFLICT, str(e))

    return MessageResponse(message="Application submitted successfully.")


@router.get("/admin/applications", response_model=ApplicationListResponse)
async def get_applications(
    status_filter: str | None = Query(None, alias="status"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> ApplicationListResponse:
    apps, total = await list_applications(status_filter=status_filter, offset=offset, limit=limit)
    return ApplicationListResponse(
        applications=[_app_to_response(a) for a in apps],
        total=total,
    )


@router.put("/admin/applications/{app_id}/review", response_model=MessageResponse)
async def review_membership_application(
    app_id: uuid.UUID,
    req: ReviewApplicationRequest,
    request: Request,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> MessageResponse:
    result = await review_application(
        app_id=app_id,
        reviewer_id=uuid.UUID(current_user["sub"]),
        action=req.action,
    )
    if result is None:
        raise AppError(
            ErrorCode.SYS_404,
            status.HTTP_404_NOT_FOUND,
            "Application not found or already reviewed.",
        )

    # Audit log — failure must not crash the endpoint
    try:
        ip = request.client.host if request.client else None
        await emit(
            "audit.action",
            user_id=current_user["sub"],
            action="APPLICATION_REVIEW",
            target_type="application",
            target_id=str(app_id),
            ip_address=ip,
        )
    except Exception as e:
        logger.error(
            "Audit log emit failed for APPLICATION_REVIEW",
            extra={"app_id": str(app_id), "error": str(e)},
        )

    return MessageResponse(message=f"Application {req.action.lower()}.")
