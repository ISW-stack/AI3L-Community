from app.schemas.user import UserResponse


def resolve_avatar_url(avatar_url: str | None) -> str | None:
    """If avatar_url is a MinIO object key (no 'http'), generate a fresh presigned URL."""
    if not avatar_url:
        return None
    if avatar_url.startswith("http://") or avatar_url.startswith("https://"):
        return avatar_url
    try:
        from app.core.storage import generate_presigned_url

        return generate_presigned_url(avatar_url, expires_in=86400 * 7)  # 7-day URL
    except Exception:
        return avatar_url


def user_to_response(user: dict) -> UserResponse:
    return UserResponse(
        id=str(user["id"]),
        username=user["username"],
        display_name=user["display_name"],
        role=user["role"],
        avatar_url=resolve_avatar_url(user.get("avatar_url")),
        orcid=user.get("orcid"),
        affiliation=user.get("affiliation"),
        bio=user.get("bio"),
        is_banned=user.get("is_banned", False),
        ban_reason=user.get("ban_reason"),
    )
