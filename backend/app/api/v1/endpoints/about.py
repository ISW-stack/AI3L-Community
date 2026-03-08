from __future__ import annotations

import asyncio
import time
import uuid
from collections import OrderedDict
from typing import Any

import requests as _requests  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.core.deps import require_role
from app.schemas.about import (
    ContributorAdminListResponse,
    ContributorAdminResponse,
    ContributorCreateRequest,
    ContributorResponse,
    ContributorsListResponse,
    ContributorUpdateRequest,
)
from app.services import contributor as contributor_service

router = APIRouter(prefix="/about", tags=["about"])

# In-memory avatar cache: contributor_id_str -> (bytes, content_type, timestamp)
_avatar_cache: OrderedDict[str, tuple[bytes, str, float]] = OrderedDict()
_CACHE_TTL_SECONDS: int = 3600  # 1 hour
_MAX_CACHE_ENTRIES: int = 50
_MAX_CACHE_BYTES: int = 10 * 1024 * 1024  # 10 MB total
_cache_total_bytes: int = 0


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

    # Check cache
    now = time.time()
    cached = _avatar_cache.get(contributor_id)
    if cached is not None:
        data, content_type, cached_at = cached
        if now - cached_at < _CACHE_TTL_SECONDS:
            _avatar_cache.move_to_end(contributor_id)
            return Response(content=data, media_type=content_type)

    # Fetch from GitHub
    github_url = f"https://github.com/{contributor['github_username']}.png"
    try:
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: _requests.get(github_url, timeout=10, allow_redirects=True),
        )

        if resp.status_code != 200:
            return Response(status_code=502, content=b"Failed to fetch avatar")

        data = resp.content
        content_type = resp.headers.get("content-type", "image/png")

        global _cache_total_bytes
        new_size = len(data)
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
        raise HTTPException(status_code=409, detail="GitHub username already exists.")

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
    if body.github_username is not None:
        existing = await contributor_service.get_contributor(contributor_id)
        if existing and existing["github_username"] != body.github_username:
            if await contributor_service.github_username_exists(body.github_username):
                raise HTTPException(status_code=409, detail="GitHub username already exists.")

    row = await contributor_service.update_contributor(
        contributor_id,
        github_username=body.github_username,
        display_name=body.display_name,
        role=body.role,
        display_order=body.display_order,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Contributor not found.")

    # Clear avatar cache if github_username changed
    global _cache_total_bytes
    cid_str = str(contributor_id)
    if body.github_username is not None and cid_str in _avatar_cache:
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
        raise HTTPException(status_code=404, detail="Contributor not found.")

    global _cache_total_bytes
    cid_str = str(contributor_id)
    if cid_str in _avatar_cache:
        _cache_total_bytes -= len(_avatar_cache[cid_str][0])
        del _avatar_cache[cid_str]

    return Response(status_code=204)
