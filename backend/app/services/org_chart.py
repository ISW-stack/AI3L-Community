import json
import uuid

from app.converters.user_converter import async_resolve_avatar_url
from app.repositories import category_repo, org_chart_repo, sig_repo, user_repo

# Cache key and TTL for the assembled org chart (full, including hidden entries).
# The endpoint filters out hidden entries per caller role before returning.
_ORG_CHART_CACHE_KEY = "about:org-chart"
_ORG_CHART_CACHE_TTL = 300  # 5 minutes


async def get_org_chart(is_super_admin: bool = False) -> dict:
    """Return org chart data.

    Non-SuperAdmin callers see only entries where is_visible=True (or no override).
    SuperAdmin callers see everything; hidden entries are included with override intact.

    The *full* assembled payload (with hidden entries) is cached in Redis for 5 min
    to avoid re-querying and re-resolving avatar URLs on every request.
    """
    from app.core.redis import get_redis  # lazy import — not available in test env

    redis = get_redis()
    cached_raw = await redis.get(_ORG_CHART_CACHE_KEY)
    if cached_raw:
        full_data: dict = json.loads(cached_raw)
    else:
        full_data = await _build_full_org_chart()
        await redis.set(_ORG_CHART_CACHE_KEY, json.dumps(full_data), ex=_ORG_CHART_CACHE_TTL)

    if is_super_admin:
        return full_data

    # Filter out hidden entries for non-SuperAdmin callers
    visible_sigs = []
    for s in full_data["sigs"]:
        if s.get("override") is not None and not s["override"].get("is_visible", True):
            continue  # whole SIG hidden
        # Filter hidden individual members within the SIG
        filtered_members = [
            m for m in s.get("members", [])
            if m.get("member_override") is None or m["member_override"].get("is_visible", True)
        ]
        visible_sigs.append({**s, "members": filtered_members})

    visible_cats = [c for c in full_data["categories"] if c.get("override") is None or c["override"].get("is_visible", True)]
    return {"sigs": visible_sigs, "categories": visible_cats}


async def invalidate_org_chart_cache() -> None:
    """Delete the cached org chart so the next request rebuilds it."""
    from app.core.redis import get_redis  # lazy import

    redis = get_redis()
    await redis.delete(_ORG_CHART_CACHE_KEY)


async def _build_full_org_chart() -> dict:
    """Query DB, resolve avatar URLs, and assemble the full org chart dict."""
    sigs = await sig_repo.find_all_sigs_with_leaders()
    categories = await category_repo.find_all_with_creators()
    overrides = await org_chart_repo.find_all_overrides()

    override_map: dict[tuple[str, str], dict] = {}
    for o in overrides:
        override_map[(o["entity_type"], str(o["entity_id"]))] = o

    sig_results = []
    for s in sigs:
        sid = str(s["id"])
        override = override_map.get(("sig", sid))
        members = []
        for m in s.get("members", []):
            avatar = await async_resolve_avatar_url(m.get("avatar_url"))
            member_key = ("sig_member", str(m["user_id"]))
            member_override = override_map.get(member_key)
            members.append({
                "user_id": str(m["user_id"]),
                "display_name": m["display_name"],
                "username": m["username"],
                "avatar_url": avatar,
                "role": m["role"],
                "org_chart_bio": m.get("org_chart_bio"),
                "member_override": _format_override(member_override) if member_override else None,
            })
        sig_results.append({
            "id": sid,
            "name": s["name"],
            "description": s.get("description"),
            "org_chart_description": s.get("org_chart_description"),
            "member_count": s.get("member_count", 0),
            "members": members,
            "override": _format_override(override) if override else None,
        })

    cat_results = []
    for c in categories:
        cid = str(c["id"])
        override = override_map.get(("category", cid))
        creator_avatar = await async_resolve_avatar_url(c.get("creator_avatar_url"))
        cat_results.append({
            "id": cid,
            "name": c["name"],
            "description": c.get("description"),
            "creator_id": str(c["created_by"]) if c.get("created_by") else None,
            "creator_display_name": c.get("creator_display_name"),
            "creator_avatar_url": creator_avatar,
            "override": _format_override(override) if override else None,
        })

    return {"sigs": sig_results, "categories": cat_results}


async def get_members(
    offset: int = 0, limit: int = 24, search: str | None = None
) -> tuple[list[dict], int]:
    members, total = await user_repo.find_all_members(offset, limit, search)
    result = []
    for m in members:
        avatar = await async_resolve_avatar_url(m.get("avatar_url"))
        result.append({
            "id": str(m["id"]),
            "username": m["username"],
            "display_name": m["display_name"],
            "avatar_url": avatar,
            "role": m["role"],
            "affiliation": m.get("affiliation"),
            "bio": m.get("bio"),
        })
    return result, total


async def update_override(
    entity_type: str,
    entity_id: uuid.UUID,
    updated_by: uuid.UUID,
    custom_title: str | None = None,
    custom_description: str | None = None,
    display_order: int | None = None,
    is_visible: bool | None = None,
    *,
    provided_fields: set[str] | None = None,
) -> dict:
    result = await org_chart_repo.upsert_override(
        entity_type=entity_type,
        entity_id=entity_id,
        updated_by=updated_by,
        custom_title=custom_title,
        custom_description=custom_description,
        display_order=display_order,
        is_visible=is_visible,
        _provided_fields=provided_fields,
    )
    await invalidate_org_chart_cache()
    return result


async def update_sig_description(sig_id: uuid.UUID, description: str | None) -> bool:
    updated = await sig_repo.update_org_chart_description(sig_id, description)
    if updated:
        await invalidate_org_chart_cache()
    return updated


async def update_member_bio(sig_id: uuid.UUID, user_id: uuid.UUID, bio: str | None) -> bool:
    updated = await sig_repo.update_org_chart_bio(sig_id, user_id, bio)
    if updated:
        await invalidate_org_chart_cache()
    return updated


def _format_override(o: dict) -> dict:
    return {
        "entity_type": o["entity_type"],
        "entity_id": str(o["entity_id"]),
        "custom_title": o.get("custom_title"),
        "custom_description": o.get("custom_description"),
        "display_order": o.get("display_order", 0),
        "is_visible": o.get("is_visible", True),
    }
