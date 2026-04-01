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


def _to_member_dict(r: dict) -> dict:
    return {
        "user_id": str(r["user_id"]),
        "username": r["username"],
        "display_name": r["display_name"],
        "avatar_url": resolve_avatar_url(r["avatar_url"]),
    }


async def get_classified_members() -> list[dict]:
    """Return all categories with their members (for the About > Members page).

    The 'member' category automatically includes all active non-guest users
    who are not assigned to any other category.
    """
    rows = await mc_repo.find_all_grouped()
    counts = await mc_repo.count_by_category()
    unclassified = await mc_repo.find_unclassified_members()
    unclassified_count = len(unclassified)

    categories = []
    for cat_key in CATEGORIES:
        members = [_to_member_dict(r) for r in rows if r["category"] == cat_key]

        if cat_key == "member":
            # Append unclassified users after manually classified ones
            members.extend(_to_member_dict(r) for r in unclassified)
            count = counts.get(cat_key, 0) + unclassified_count
        else:
            count = counts.get(cat_key, 0)

        categories.append(
            {
                "key": cat_key,
                "label": CATEGORY_LABELS[cat_key],
                "count": count,
                "members": members,
            }
        )
    return categories


async def get_category_members(category: str) -> list[dict]:
    """Return members in a single category.

    For 'member', also includes unclassified active non-guest users.
    """
    if category not in CATEGORIES:
        raise ValidationError(f"Invalid category: {category}")

    rows = await mc_repo.find_by_category(category)
    members = [_to_member_dict(r) for r in rows]

    if category == "member":
        unclassified = await mc_repo.find_unclassified_members()
        members.extend(_to_member_dict(r) for r in unclassified)

    return members


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
