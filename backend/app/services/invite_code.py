"""Invite code listing service."""

from datetime import datetime, timezone

from app.repositories import invite_code_repo


async def list_invite_codes(
    status_filter: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[dict], int]:
    """Return paginated invite codes with status derived from consumed_at/expires_at."""
    rows, total = await invite_code_repo.find_many(status_filter, offset, limit)

    codes = []
    for row in rows:
        if row.get("consumed_at"):
            row["status"] = "consumed"
        elif row.get("expires_at") and row["expires_at"].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            row["status"] = "expired"
        else:
            row["status"] = "active"
        codes.append(row)

    return codes, total
