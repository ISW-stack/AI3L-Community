from __future__ import annotations

import asyncio
import time
import uuid
from collections import OrderedDict
from typing import Any

import requests as _requests  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.deps import require_role
from app.core.errors import AppError, ErrorCode
from app.core.rate_limit import check_rate_limit
from app.repositories import sig_repo
from app.schemas.about import (
    ContributorAdminListResponse,
    ContributorAdminResponse,
    ContributorCreateRequest,
    ContributorResponse,
    ContributorsListResponse,
    ContributorUpdateRequest,
)
from app.schemas.org_chart import (
    MemberCardResponse,
    MemberOrgChartBioUpdateRequest,
    MembersListResponse,
    OrgChartOverrideResponse,
    OrgChartOverrideUpdateRequest,
    OrgChartResponse,
    SigOrgChartDescriptionUpdateRequest,
)
from app.services import contributor as contributor_service
from app.services import org_chart as org_chart_service
from app.services import site_settings as site_settings_service

router = APIRouter(prefix="/about", tags=["about"])

# In-memory avatar cache: contributor_id_str -> (bytes, content_type, timestamp)
_avatar_cache: OrderedDict[str, tuple[bytes, str, float]] = OrderedDict()
_CACHE_TTL_SECONDS: int = 3600  # 1 hour
_MAX_CACHE_ENTRIES: int = 50
_MAX_CACHE_BYTES: int = 10 * 1024 * 1024  # 10 MB total
_MAX_AVATAR_DOWNLOAD_BYTES: int = 5 * 1024 * 1024  # 5 MB per avatar
_cache_total_bytes: int = 0
_cache_lock = asyncio.Lock()


def _build_avatar_url(contributor_id: str) -> str:
    return f"/api/v1/about/contributors/{contributor_id}/avatar"


@router.get("/contributors", response_model=ContributorsListResponse)
async def list_contributors(
    _current_user: dict[str, Any] = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> ContributorsListResponse:
    """Return the list of project contributors with proxied avatar URLs."""
    rows = await contributor_service.list_contributors()
    contributors = [
        ContributorResponse(
            id=str(row["id"]),
            display_name=row["display_name"],
            role=row["role"],
            avatar_url=_build_avatar_url(str(row["id"])),
        )
        for row in rows
    ]
    return ContributorsListResponse(contributors=contributors)


@router.get("/contributors/{contributor_id}/avatar")
async def get_contributor_avatar(
    contributor_id: str,
    _current_user: dict[str, Any] = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> Response:
    """Proxy a contributor's GitHub avatar to hide the GitHub username."""
    try:
        cid = uuid.UUID(contributor_id)
    except ValueError:
        return Response(status_code=404, content=b"Contributor not found")

    contributor = await contributor_service.get_contributor(cid)
    if contributor is None:
        return Response(status_code=404, content=b"Contributor not found")

    # Check cache (under lock for thread safety)
    global _cache_total_bytes
    now = time.time()
    async with _cache_lock:
        cached = _avatar_cache.get(contributor_id)
        if cached is not None:
            data, content_type, cached_at = cached
            if now - cached_at < _CACHE_TTL_SECONDS:
                _avatar_cache.move_to_end(contributor_id)
                return Response(content=data, media_type=content_type)
            # Evict expired entry immediately so it stops consuming memory
            _cache_total_bytes -= len(data)
            del _avatar_cache[contributor_id]

    # Rate-limit outbound GitHub fetches per user: 30 requests per 60 seconds
    user_id = _current_user.get("sub", contributor_id)
    if not await check_rate_limit(f"rl:avatar:{user_id}", 30, 60):
        raise AppError(ErrorCode.SYS_429, 429, "Too many avatar requests.")

    # Fetch from GitHub — allow_redirects=True handles multi-level redirects.
    # SSRF is not a concern since the URL is derived from a hardcoded GitHub
    # domain and the contributor's github_username stored in our database.
    github_url = f"https://github.com/{contributor['github_username']}.png"
    try:
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: _requests.get(
                github_url, timeout=10, allow_redirects=True, stream=True
            ),
        )

        if resp.status_code != 200:
            resp.close()
            return Response(status_code=502, content=b"Failed to fetch avatar")

        content_type = resp.headers.get("content-type", "image/png")
        if not content_type.startswith("image/"):
            resp.close()
            return Response(status_code=502, content=b"Invalid content type from upstream")

        # Enforce download size limit to prevent memory exhaustion
        content_length_raw = resp.headers.get("content-length")
        try:
            content_length = int(content_length_raw) if content_length_raw else 0
        except (ValueError, TypeError):
            content_length = 0
        if content_length > _MAX_AVATAR_DOWNLOAD_BYTES:
            resp.close()
            return Response(status_code=502, content=b"Avatar too large")

        # L-14: Stream with size limit instead of loading full body into memory
        chunks: list[bytes] = []
        total_downloaded = 0
        for chunk in resp.iter_content(8192):
            total_downloaded += len(chunk)
            if total_downloaded > _MAX_AVATAR_DOWNLOAD_BYTES:
                resp.close()
                return Response(status_code=502, content=b"Avatar too large")
            chunks.append(chunk)
        resp.close()
        data = b"".join(chunks)

        new_size = len(data)
        async with _cache_lock:
            # Evict oldest entries until there is room (byte limit)
            while _avatar_cache and _cache_total_bytes + new_size > _MAX_CACHE_BYTES:
                _oldest_key, _oldest_val = _avatar_cache.popitem(last=False)
                _cache_total_bytes -= len(_oldest_val[0])
            # Evict oldest entry if count limit reached
            if len(_avatar_cache) >= _MAX_CACHE_ENTRIES:
                _oldest_key, _oldest_val = _avatar_cache.popitem(last=False)
                _cache_total_bytes -= len(_oldest_val[0])
            _avatar_cache[contributor_id] = (data, content_type, now)
            _avatar_cache.move_to_end(contributor_id)
            _cache_total_bytes += new_size

        return Response(content=data, media_type=content_type)
    except _requests.RequestException:
        return Response(status_code=502, content=b"Failed to fetch avatar")


# ── Org Chart & Members ────────────────────────────────────────────────


@router.get("/org-chart", response_model=OrgChartResponse)
async def get_org_chart(
    current_user: dict[str, Any] = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> OrgChartResponse:
    """Return org chart data: SIGs with leaders and forum categories with creators.

    Hidden entries (is_visible=False) are only returned to SUPER_ADMIN callers.
    """
    is_super_admin = current_user.get("role") == "SUPER_ADMIN"
    data = await org_chart_service.get_org_chart(is_super_admin=is_super_admin)
    return OrgChartResponse(**data)


@router.get("/members", response_model=MembersListResponse)
async def list_members(
    page: int = Query(1, ge=1, le=1000),
    page_size: int = Query(24, ge=1, le=100),
    search: str = Query("", max_length=200),
    _current_user: dict[str, Any] = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> MembersListResponse:
    """Return paginated list of all non-guest members."""
    offset = (page - 1) * page_size
    members, total = await org_chart_service.get_members(
        offset=offset, limit=page_size, search=search or None
    )
    return MembersListResponse(members=[MemberCardResponse(**m) for m in members], total=total)


@router.put("/org-chart/override/{entity_type}/{entity_id}")
async def update_override(
    entity_type: str,
    entity_id: uuid.UUID,
    body: OrgChartOverrideUpdateRequest,
    current_user: dict[str, Any] = Depends(require_role("SUPER_ADMIN")),
) -> OrgChartOverrideResponse:
    """Update org chart override (title, order, visibility). SUPER_ADMIN only."""
    if entity_type not in ("sig", "category", "sig_member"):
        raise AppError(ErrorCode.SYS_422, 422, "Invalid entity_type.")

    # Determine which fields were explicitly sent in the JSON body so the
    # repository can distinguish "not provided" from "set to null".
    # L-05: Use model_fields_set instead of double-parsing the request body.
    provided_fields = body.model_fields_set & {
        "custom_title",
        "custom_description",
        "display_order",
        "is_visible",
    }

    result = await org_chart_service.update_override(
        entity_type=entity_type,
        entity_id=entity_id,
        updated_by=uuid.UUID(current_user["sub"]),
        custom_title=body.custom_title,
        custom_description=body.custom_description,
        display_order=body.display_order,
        is_visible=body.is_visible,
        provided_fields=provided_fields,
    )
    return OrgChartOverrideResponse(
        entity_type=result["entity_type"],
        entity_id=str(result["entity_id"]),
        custom_title=result.get("custom_title"),
        custom_description=result.get("custom_description"),
        display_order=result.get("display_order", 0),
        is_visible=result.get("is_visible", True),
    )


@router.put("/org-chart/sigs/{sig_id}/description")
async def update_sig_org_chart_description(
    sig_id: uuid.UUID,
    body: SigOrgChartDescriptionUpdateRequest,
    current_user: dict[str, Any] = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> dict[str, str]:
    """Update a SIG's org chart description. SIG ADMIN or SUB_ADMIN only."""
    user_id = uuid.UUID(current_user["sub"])
    user_role = current_user.get("role", "")

    if user_role != "SUPER_ADMIN":
        sig_role = await sig_repo.get_member_role(sig_id, user_id)
        if sig_role not in ("ADMIN", "SUB_ADMIN"):
            raise AppError(ErrorCode.SYS_403, 403, "Only SIG admins can edit this.")

    updated = await org_chart_service.update_sig_description(sig_id, body.org_chart_description)
    if not updated:
        raise AppError(ErrorCode.SYS_404, 404, "SIG not found.")
    return {"status": "ok"}


@router.put("/org-chart/sigs/{sig_id}/members/me/bio")
async def update_my_org_chart_bio(
    sig_id: uuid.UUID,
    body: MemberOrgChartBioUpdateRequest,
    current_user: dict[str, Any] = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> dict[str, str]:
    """Update the caller's org_chart_bio for a specific SIG."""
    user_id = uuid.UUID(current_user["sub"])
    sig_role = await sig_repo.get_member_role(sig_id, user_id)
    if sig_role is None:
        raise AppError(ErrorCode.SYS_403, 403, "You are not a member of this SIG.")

    updated = await org_chart_service.update_member_bio(sig_id, user_id, body.org_chart_bio)
    if not updated:
        raise AppError(ErrorCode.SYS_404, 404, "Membership not found.")
    return {"status": "ok"}


# ── About Introduction (photo + bio) ──────────────────────────────────


@router.get("/intro")
async def get_about_intro(
    _current_user: dict[str, Any] = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> dict[str, str]:
    """Return the about introduction photo URL and bio text."""
    data = await site_settings_service.get_about_intro()
    photo_url = ""
    if data["photo_key"]:
        from app.core.storage import generate_presigned_url

        photo_url = generate_presigned_url(data["photo_key"])
    return {"photo_url": photo_url, "bio": data["bio"]}


_MAX_INTRO_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

# Magic byte signatures for image validation
_IMAGE_MAGIC: dict[bytes, str] = {
    b"\xff\xd8\xff": "jpg",
    b"\x89PNG": "png",
    b"RIFF": "webp",  # WebP starts with RIFF....WEBP
}


def _detect_image_ext(data: bytes) -> str | None:
    """Return file extension from magic bytes, or None if not a known image."""
    if len(data) < 12:
        return None
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:4] == b"\x89PNG":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


class _BioUpdateRequest(BaseModel):
    bio: str = Field(default="", max_length=5000)


@router.put("/admin/intro/photo")
async def update_about_intro_photo(
    file: UploadFile,
    _current_user: dict[str, Any] = Depends(require_role("SUPER_ADMIN")),
) -> dict[str, str]:
    """Upload or replace the about introduction photo. SUPER_ADMIN only."""
    if file.content_type not in _ALLOWED_IMAGE_TYPES:
        raise AppError(ErrorCode.SYS_422, 422, "Only JPEG, PNG, or WebP images are allowed.")

    data = await file.read(_MAX_INTRO_PHOTO_BYTES + 1)
    if len(data) > _MAX_INTRO_PHOTO_BYTES:
        raise AppError(
            ErrorCode.FILE_001,
            413,
            f"File too large (max {_MAX_INTRO_PHOTO_BYTES // (1024*1024)} MB).",
        )

    # Validate actual file content via magic bytes (don't trust client content_type)
    ext = _detect_image_ext(data)
    if ext is None:
        raise AppError(ErrorCode.SYS_422, 422, "File content is not a valid image.")

    key = f"site/about-intro-{uuid.uuid4()}.{ext}"

    from app.core.storage import delete_file, generate_presigned_url, upload_file

    # Delete old photo from storage if one exists
    old_data = await site_settings_service.get_about_intro()
    old_key = old_data["photo_key"]

    loop = asyncio.get_running_loop()
    # M-07: Wrap synchronous boto3 calls in executor to avoid blocking the event loop
    await loop.run_in_executor(None, upload_file, data, key, file.content_type or "image/jpeg")
    await site_settings_service.update_about_intro_photo(key)

    if old_key:
        try:
            await loop.run_in_executor(None, delete_file, old_key)
        except Exception:
            pass  # best-effort cleanup; orphan file cleaner will catch it

    photo_url = await loop.run_in_executor(None, generate_presigned_url, key)
    return {"photo_url": photo_url}


@router.put("/admin/intro/bio")
async def update_about_intro_bio(
    body: _BioUpdateRequest,
    _current_user: dict[str, Any] = Depends(require_role("SUPER_ADMIN")),
) -> dict[str, str]:
    """Update the about introduction bio text. SUPER_ADMIN only."""
    await site_settings_service.update_about_intro_bio(body.bio)
    return {"status": "ok"}


# ── Admin CRUD (SUPER_ADMIN only) ──────────────────────────────────────


@router.get("/admin/contributors", response_model=ContributorAdminListResponse)
async def admin_list_contributors(
    _current_user: dict[str, Any] = Depends(require_role("SUPER_ADMIN")),
) -> ContributorAdminListResponse:
    """List all contributors with full details (admin)."""
    rows = await contributor_service.list_contributors()
    contributors = [
        ContributorAdminResponse(
            id=str(row["id"]),
            github_username=row["github_username"],
            display_name=row["display_name"],
            role=row["role"],
            display_order=row["display_order"],
            avatar_url=_build_avatar_url(str(row["id"])),
            created_at=row["created_at"],
        )
        for row in rows
    ]
    return ContributorAdminListResponse(contributors=contributors)


@router.post("/admin/contributors", response_model=ContributorAdminResponse, status_code=201)
async def admin_create_contributor(
    body: ContributorCreateRequest,
    _current_user: dict[str, Any] = Depends(require_role("SUPER_ADMIN")),
) -> ContributorAdminResponse:
    """Create a new contributor."""
    if await contributor_service.github_username_exists(body.github_username):
        raise AppError(ErrorCode.SYS_409, 409, "GitHub username already exists.")

    row = await contributor_service.create_contributor(
        github_username=body.github_username,
        display_name=body.display_name,
        role=body.role,
        display_order=body.display_order,
    )
    return ContributorAdminResponse(
        id=str(row["id"]),
        github_username=row["github_username"],
        display_name=row["display_name"],
        role=row["role"],
        display_order=row["display_order"],
        avatar_url=_build_avatar_url(str(row["id"])),
        created_at=row["created_at"],
    )


@router.put("/admin/contributors/{contributor_id}", response_model=ContributorAdminResponse)
async def admin_update_contributor(
    contributor_id: uuid.UUID,
    body: ContributorUpdateRequest,
    _current_user: dict[str, Any] = Depends(require_role("SUPER_ADMIN")),
) -> ContributorAdminResponse:
    """Update an existing contributor."""
    global _cache_total_bytes
    github_username_changed = False
    if body.github_username is not None:
        existing = await contributor_service.get_contributor(contributor_id)
        if existing and existing["github_username"] != body.github_username:
            github_username_changed = True
            if await contributor_service.github_username_exists(body.github_username):
                raise AppError(ErrorCode.SYS_409, 409, "GitHub username already exists.")

    row = await contributor_service.update_contributor(
        contributor_id,
        github_username=body.github_username,
        display_name=body.display_name,
        role=body.role,
        display_order=body.display_order,
    )
    if row is None:
        raise AppError(ErrorCode.SYS_404, 404, "Contributor not found.")

    # Clear avatar cache only if github_username actually changed
    if github_username_changed:
        cid_str = str(contributor_id)
        async with _cache_lock:
            if cid_str in _avatar_cache:
                _cache_total_bytes -= len(_avatar_cache[cid_str][0])
                del _avatar_cache[cid_str]

    return ContributorAdminResponse(
        id=str(row["id"]),
        github_username=row["github_username"],
        display_name=row["display_name"],
        role=row["role"],
        display_order=row["display_order"],
        avatar_url=_build_avatar_url(str(row["id"])),
        created_at=row["created_at"],
    )


@router.delete("/admin/contributors/{contributor_id}", status_code=204)
async def admin_delete_contributor(
    contributor_id: uuid.UUID,
    _current_user: dict[str, Any] = Depends(require_role("SUPER_ADMIN")),
) -> Response:
    """Delete a contributor."""
    deleted = await contributor_service.delete_contributor(contributor_id)
    if not deleted:
        raise AppError(ErrorCode.SYS_404, 404, "Contributor not found.")

    global _cache_total_bytes
    cid_str = str(contributor_id)
    async with _cache_lock:
        if cid_str in _avatar_cache:
            _cache_total_bytes -= len(_avatar_cache[cid_str][0])
            del _avatar_cache[cid_str]

    return Response(status_code=204)
