from __future__ import annotations

import uuid

from loguru import logger

from app.converters.user_converter import resolve_avatar_url
from app.core.errors import ValidationError
from app.repositories import member_classification_repo as mc_repo
from app.repositories.member_classification_repo import CATEGORIES

CATEGORY_LABELS: dict[str, str] = {
    "chair": "Chair",
    "co_chair": "Co-Chair(s)",
    "ec_member": "EC Members",
    "sig_chair": "SIG Chairs",
    "sre": "Site Reliability Engineer",
    "member": "Members",
}


async def get_classified_members() -> list[dict]:
    """Return all categories with their members (for the About > Members page)."""
    rows = await mc_repo.find_all_grouped()
    counts = await mc_repo.count_by_category()

    categories = []
    for cat_key in CATEGORIES:
        members = []
        for r in rows:
            if r["category"] == cat_key:
                members.append(
                    {
                        "user_id": str(r["user_id"]),
                        "username": r["username"],
                        "display_name": r["display_name"],
                        "avatar_url": resolve_avatar_url(r["avatar_url"]),
                    }
                )
        categories.append(
            {
                "key": cat_key,
                "label": CATEGORY_LABELS[cat_key],
                "count": counts.get(cat_key, 0),
                "members": members,
            }
        )
    return categories


async def get_category_members(category: str) -> list[dict]:
    """Return members in a single category."""
    if category not in CATEGORIES:
        raise ValidationError(f"Invalid category: {category}")
    rows = await mc_repo.find_by_category(category)
    return [
        {
            "user_id": str(r["user_id"]),
            "username": r["username"],
            "display_name": r["display_name"],
            "avatar_url": resolve_avatar_url(r["avatar_url"]),
        }
        for r in rows
    ]


async def assign_classification(
    user_id: uuid.UUID,
    category: str,
    display_order: int,
    assigned_by: uuid.UUID,
) -> dict:
    """Assign or update a user's classification. Chair category limited to 1."""
    if category not in CATEGORIES:
        raise ValidationError(f"Invalid category: {category}")

    # Chair limited to 1 person
    if category == "chair":
        current_count = await mc_repo.count_in_category("chair")
        existing = await mc_repo.find_by_user_id(user_id)
        already_chair = existing and existing["category"] == "chair"
        if current_count >= 1 and not already_chair:
            raise ValidationError(
                "Chair category is limited to 1 person. Remove the current Chair first."
            )

    result = await mc_repo.upsert(user_id, category, display_order, assigned_by)
    logger.info(
        "Member classification assigned",
        extra={"user_id": str(user_id), "category": category},
    )
    return result


async def remove_classification(user_id: uuid.UUID) -> bool:
    """Remove a user's classification."""
    deleted = await mc_repo.delete_by_user_id(user_id)
    if deleted:
        logger.info("Member classification removed", extra={"user_id": str(user_id)})
    return deleted
