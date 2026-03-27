"""Admin dashboard, invite code management, and IP ban endpoints."""

import ipaddress
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request, Response, status
from loguru import logger
from pydantic import BaseModel, Field

from app.core.rate_limit import get_client_ip

from app.core.deps import require_role
from app.core.errors import AppError, ErrorCode
from app.repositories import invite_code_repo
from app.services.dashboard import get_dashboard_stats
from app.services.invite_code import list_invite_codes


class IpBanRequest(BaseModel):
    ip_address: str = Field(..., max_length=45)
    reason: str = Field("", max_length=500)
    expires_at: datetime | None = None


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard")
async def dashboard(
    current_user: dict = Depends(require_role("SUPER_ADMIN", "ADMIN")),
) -> dict:
    stats = await get_dashboard_stats()
    return stats


@router.get("/invite-codes")
async def get_invite_codes(
    status_filter: str | None = Query(None, alias="status", pattern="^(active|consumed|expired)$"),
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
    # M-08: Atomically revoke with ownership filter to prevent TOCTOU race.
    if current_user["role"] != "SUPER_ADMIN":
        from app.core.database import get_pool

        pool = get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE invite_codes SET expires_at = NOW() "
                "WHERE id = $1 AND consumed_at IS NULL AND expires_at > NOW() AND created_by = $2",
                code_id,
                uuid.UUID(current_user["sub"]),
            )
        if result and result.endswith(" 0"):
            # Could be not found, not owned, or already consumed/expired
            code_info = await invite_code_repo.find_by_id(code_id)
            if code_info and str(code_info.get("created_by")) != current_user["sub"]:
                raise AppError(
                    ErrorCode.SYS_403,
                    status.HTTP_403_FORBIDDEN,
                    "You can only revoke your own invite codes.",
                )
            raise AppError(
                ErrorCode.SYS_404,
                status.HTTP_404_NOT_FOUND,
                "Invite code not found or already consumed/expired.",
            )
        revoked = True
    else:
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

        ip = get_client_ip(request)
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
    # M-08: Atomically delete with ownership filter to prevent TOCTOU race.
    if current_user["role"] != "SUPER_ADMIN":
        from app.core.database import get_pool

        pool = get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM invite_codes WHERE id = $1 AND created_by = $2",
                code_id,
                uuid.UUID(current_user["sub"]),
            )
        if result and result.endswith(" 0"):
            # Could be not found or not owned
            code_info = await invite_code_repo.find_by_id(code_id)
            if code_info and str(code_info.get("created_by")) != current_user["sub"]:
                raise AppError(
                    ErrorCode.SYS_403,
                    status.HTTP_403_FORBIDDEN,
                    "You can only delete your own invite codes.",
                )
            raise AppError(ErrorCode.SYS_404, status.HTTP_404_NOT_FOUND, "Invite code not found.")
        deleted = True
    else:
        deleted = await invite_code_repo.delete(code_id)
    if not deleted:
        raise AppError(ErrorCode.SYS_404, status.HTTP_404_NOT_FOUND, "Invite code not found.")
    # Audit log — failure must not crash the endpoint
    try:
        from app.core.event_bus import emit

        ip = get_client_ip(request)
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


# --- IP Ban endpoints (SUPER_ADMIN only) ---


@router.get("/ip-bans")
async def list_ip_bans(
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(require_role("SUPER_ADMIN")),
) -> dict:
    """List all IP bans (paginated)."""
    from app.services.ip_ban import list_ip_bans as list_bans

    bans, total = await list_bans(page=page, page_size=page_size)
    # Serialize UUIDs and datetimes for JSON response
    serialized = []
    for ban in bans:
        serialized.append(
            {
                "id": str(ban["id"]),
                "ip_address": ban["ip_address"],
                "reason": ban.get("reason", ""),
                "banned_by": str(ban["banned_by"]) if ban.get("banned_by") else None,
                "expires_at": ban["expires_at"].isoformat() if ban.get("expires_at") else None,
                "created_at": ban["created_at"].isoformat() if ban.get("created_at") else None,
            }
        )
    return {"bans": serialized, "total": total, "page": page, "page_size": page_size}


@router.post("/ip-bans", status_code=status.HTTP_201_CREATED)
async def ban_ip(
    req: IpBanRequest,
    request: Request,
    current_user: dict = Depends(require_role("SUPER_ADMIN")),
) -> dict:
    """Ban an IP address."""
    # Validate IP address format
    try:
        ipaddress.ip_address(req.ip_address)
    except ValueError:
        raise AppError(ErrorCode.SYS_422, 422, "Invalid IP address format.")

    from app.services.ip_ban import ban_ip as ban_ip_svc

    ban = await ban_ip_svc(
        ip=req.ip_address,
        reason=req.reason,
        banned_by=uuid.UUID(current_user["sub"]),
        expires_at=req.expires_at,
    )

    # Audit log
    try:
        from app.core.event_bus import emit

        ip = get_client_ip(request)
        await emit(
            "audit.action",
            user_id=current_user["sub"],
            action="IP_BAN",
            target_type="ip",
            target_id=req.ip_address,
            ip_address=ip,
            detail=req.reason or None,
        )
    except Exception as e:
        logger.error(
            "Audit log emit failed for IP_BAN",
            extra={"ip_address": req.ip_address, "error": str(e)},
        )

    return {
        "id": str(ban["id"]),
        "ip_address": ban["ip_address"],
        "reason": ban.get("reason", ""),
        "banned_by": str(ban["banned_by"]) if ban.get("banned_by") else None,
        "expires_at": ban["expires_at"].isoformat() if ban.get("expires_at") else None,
        "created_at": ban["created_at"].isoformat() if ban.get("created_at") else None,
    }


@router.delete("/ip-bans/{ban_id}", status_code=status.HTTP_200_OK)
async def unban_ip(
    ban_id: uuid.UUID,
    request: Request,
    current_user: dict = Depends(require_role("SUPER_ADMIN")),
) -> dict:
    """Remove an IP ban."""
    from app.services.ip_ban import unban_ip as unban_ip_svc

    deleted = await unban_ip_svc(ban_id)
    if not deleted:
        raise AppError(ErrorCode.SYS_404, 404, "IP ban not found.")

    # Audit log
    try:
        from app.core.event_bus import emit

        ip = get_client_ip(request)
        await emit(
            "audit.action",
            user_id=current_user["sub"],
            action="IP_UNBAN",
            target_type="ip",
            target_id=str(ban_id),
            ip_address=ip,
        )
    except Exception as e:
        logger.error(
            "Audit log emit failed for IP_UNBAN",
            extra={"ban_id": str(ban_id), "error": str(e)},
        )

    return {"message": "IP ban removed."}
