import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from loguru import logger

from app.core.constants import RATE_LIMIT_APPLY_MEMBER, RATE_LIMIT_REVIEW_APPLICATION
from app.core.deps import get_current_user, require_role
from app.core.errors import AppError, ErrorCode
from app.core.event_bus import emit
from app.core.logging_utils import safe_error_detail
from app.core.rate_limit import check_rate_limit, get_client_ip
from app.core.security import validate_password_policy
from app.schemas.application import (
    ApplicationListResponse,
    ApplicationResponse,
    ReviewApplicationRequest,
)
from app.schemas.auth import MessageResponse
from app.schemas.user import ApplyMemberRequest
from app.services.application import (
    create_application,
    list_applications,
    review_application,
)

router = APIRouter(tags=["applications"])


def _app_to_response(app: dict) -> ApplicationResponse:
    return ApplicationResponse(
        id=str(app["id"]),
        user_id=str(app["user_id"]),
        username=app["username"],
        display_name=app["display_name"],
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
    if not await check_rate_limit(
        f"rl:apply_member:{current_user['sub']}", *RATE_LIMIT_APPLY_MEMBER
    ):
        raise AppError(ErrorCode.SYS_429, 429, "Too many applications. Try again later.")

    if current_user["role"] != "GUEST":
        raise AppError(
            ErrorCode.SYS_422,
            422,
            "Only guests can apply for membership.",
        )

    # Validate password policy
    pw_error = validate_password_policy(req.password)
    if pw_error:
        raise AppError(ErrorCode.AUTH_007, status.HTTP_400_BAD_REQUEST, pw_error)

    # Username uniqueness is enforced atomically by the DB unique constraint.
    # The service layer catches UniqueViolationError and raises ValueError.

    # Note: The guest's JWT (sub, role, jti) remains valid even after the DB user
    # record is created by insert_with_user(). get_current_user reads from the JWT
    # and doesn't re-query the DB. The role in the JWT stays "GUEST" until the
    # application is approved and the guest re-logs in with MEMBER role.
    try:
        await create_application(
            guest_id=uuid.UUID(current_user["sub"]),
            username=req.username,
            password=req.password,
            display_name=req.display_name,
            description=req.description,
        )
    except ValueError as e:
        raise AppError(ErrorCode.SYS_409, status.HTTP_409_CONFLICT, safe_error_detail(e, "Application conflict."))

    return MessageResponse(message="Application submitted successfully.")


@router.get("/admin/applications", response_model=ApplicationListResponse)
async def get_applications(
    status_filter: str | None = Query(
        None, alias="status", pattern="^(PENDING|APPROVED|REJECTED)$"
    ),
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
    if not await check_rate_limit(
        f"rl:review_app:{current_user['sub']}", *RATE_LIMIT_REVIEW_APPLICATION
    ):
        raise AppError(ErrorCode.SYS_429, status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests.")
    try:
        result = await review_application(
            app_id=app_id,
            reviewer_id=uuid.UUID(current_user["sub"]),
            action=req.action,
        )
    except ValueError as e:
        # The ReviewApplicationRequest schema validates action via pattern, so
        # invalid actions get 422 before reaching here. This ValueError comes
        # from update_status() when the user role upgrade fails (e.g. user was
        # deleted or is no longer a GUEST). 409 is appropriate since the
        # resource state conflicts with the requested operation.
        raise AppError(ErrorCode.SYS_409, status.HTTP_409_CONFLICT, safe_error_detail(e, "Review conflict."))
    if result is None:
        raise AppError(
            ErrorCode.SYS_404,
            status.HTTP_404_NOT_FOUND,
            "Application not found or already reviewed.",
        )

    # Audit log — failure must not crash the endpoint
    try:
        ip = get_client_ip(request)
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
