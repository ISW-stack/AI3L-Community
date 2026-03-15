"""Admin dashboard and invite code management endpoints."""

import uuid

from fastapi import APIRouter, Depends, Query, Request, Response, status
from loguru import logger

from app.core.deps import require_role
from app.core.errors import AppError, ErrorCode
from app.repositories import invite_code_repo
from app.services.dashboard import get_dashboard_stats
from app.services.invite_code import list_invite_codes

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard")
async def dashboard(
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> dict:
    stats = await get_dashboard_stats()
    return stats


@router.get("/invite-codes")
async def get_invite_codes(
    status_filter: str | None = Query(None, alias="status"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> dict:
    codes, total = await list_invite_codes(status_filter=status_filter, offset=offset, limit=limit)
    return {"codes": codes, "total": total}


@router.patch("/invite-codes/{code_id}/revoke", status_code=status.HTTP_200_OK)
async def revoke_invite_code(
    code_id: uuid.UUID,
    request: Request,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> dict:
    revoked = await invite_code_repo.revoke(code_id)
    if not revoked:
        raise AppError(
            ErrorCode.SYS_404,
            status.HTTP_404_NOT_FOUND,
            "Invite code not found or already consumed/expired.",
        )
    # Audit log — failure must not crash the endpoint
    try:
        from app.core.event_bus import emit

        ip = request.client.host if request.client else None
        await emit(
            "audit.action",
            user_id=current_user["sub"],
            action="INVITE_CODE_REVOKE",
            ip_address=ip,
            detail=str(code_id),
        )
    except Exception as e:
        logger.error(
            "Audit log emit failed for INVITE_CODE_REVOKE",
            extra={"code_id": str(code_id), "error": str(e)},
        )
    return {"message": "Invite code revoked."}


@router.delete("/invite-codes/{code_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invite_code(
    code_id: uuid.UUID,
    request: Request,
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> Response:
    deleted = await invite_code_repo.delete(code_id)
    if not deleted:
        raise AppError(ErrorCode.SYS_404, status.HTTP_404_NOT_FOUND, "Invite code not found.")
    # Audit log — failure must not crash the endpoint
    try:
        from app.core.event_bus import emit

        ip = request.client.host if request.client else None
        await emit(
            "audit.action",
            user_id=current_user["sub"],
            action="INVITE_CODE_DELETE",
            ip_address=ip,
            detail=str(code_id),
        )
    except Exception as e:
        logger.error(
            "Audit log emit failed for INVITE_CODE_DELETE",
            extra={"code_id": str(code_id), "error": str(e)},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
