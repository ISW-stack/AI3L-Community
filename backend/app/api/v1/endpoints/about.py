from __future__ import annotations

import asyncio
import time
from typing import Any

import requests as _requests  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.core.deps import require_role
from app.schemas.about import ContributorResponse, ContributorsListResponse

router = APIRouter(prefix="/about", tags=["about"])

_CONTRIBUTORS: list[dict[str, Any]] = [
    {
        "id": 0,
        "display_name": "Isaries",
        "role": "Project Lead & Full-Stack Developer",
        "github": "Isaries",
    },
    {
        "id": 1,
        "display_name": "SW9526",
        "role": "Frontend Contributor",
        "github": "SW9526",
    },
]

# In-memory avatar cache: contributor_id -> (bytes, content_type, timestamp)
_avatar_cache: dict[int, tuple[bytes, str, float]] = {}
_CACHE_TTL_SECONDS: int = 3600  # 1 hour


@router.get("/contributors", response_model=ContributorsListResponse)
async def list_contributors(
    _current_user: dict[str, Any] = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> ContributorsListResponse:
    """Return the list of project contributors with proxied avatar URLs."""
    contributors: list[ContributorResponse] = []

    for c in _CONTRIBUTORS:
        # Use a root-relative path so the browser resolves it against its own origin.
        # This avoids Docker-internal hostnames leaking into the response.
        avatar_url = f"/api/v1/about/contributors/{c['id']}/avatar"
        contributors.append(
            ContributorResponse(
                id=c["id"],
                display_name=c["display_name"],
                role=c["role"],
                avatar_url=avatar_url,
            )
        )

    return ContributorsListResponse(contributors=contributors)


@router.get("/contributors/{contributor_id}/avatar")
async def get_contributor_avatar(
    contributor_id: int,
    _current_user: dict[str, Any] = Depends(require_role("MEMBER", "ADMIN", "SUPER_ADMIN")),
) -> Response:
    """Proxy a contributor's GitHub avatar to hide the GitHub username."""
    # Find contributor
    contributor: dict[str, Any] | None = None
    for c in _CONTRIBUTORS:
        if c["id"] == contributor_id:
            contributor = c
            break

    if contributor is None:
        return Response(status_code=404, content=b"Contributor not found")

    # Check cache
    now = time.time()
    cached = _avatar_cache.get(contributor_id)
    if cached is not None:
        data, content_type, cached_at = cached
        if now - cached_at < _CACHE_TTL_SECONDS:
            return Response(content=data, media_type=content_type)

    # Fetch from GitHub (run sync requests in thread pool to avoid blocking event loop)
    github_url = f"https://github.com/{contributor['github']}.png"
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

        # Store in cache
        _avatar_cache[contributor_id] = (data, content_type, now)

        return Response(content=data, media_type=content_type)
    except _requests.RequestException:
        return Response(status_code=502, content=b"Failed to fetch avatar")
