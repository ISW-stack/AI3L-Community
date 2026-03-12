from app.schemas.user import PublicUserResponse, UserResponse


def resolve_avatar_url(avatar_url: str | None) -> str | None:
    """If avatar_url is a MinIO object key (no 'http'), generate a fresh presigned URL.

    Synchronous version — use in non-async contexts (e.g. Celery tasks).
    For async endpoint handlers, prefer async_resolve_avatar_url().
    """
    if not avatar_url:
        return None
    if avatar_url.startswith("http://") or avatar_url.startswith("https://"):
        return avatar_url
    try:
        from app.core.storage import generate_presigned_url

        return generate_presigned_url(avatar_url, expires_in=86400 * 7)  # 7-day URL
    except Exception:
        return avatar_url


async def async_resolve_avatar_url(avatar_url: str | None) -> str | None:
    """Async version of resolve_avatar_url that does not block the event loop.

    Runs the synchronous boto3 presigned URL generation in a thread executor.
    """
    if not avatar_url:
        return None
    if avatar_url.startswith("http://") or avatar_url.startswith("https://"):
        return avatar_url
    try:
        from app.core.async_storage import generate_presigned_url

        return await generate_presigned_url(avatar_url, expires_in=86400 * 7)  # 7-day URL
    except Exception:
        return avatar_url


def user_to_public_response(user: dict) -> PublicUserResponse:
    return PublicUserResponse(
        id=str(user["id"]),
        username=user["username"],
        display_name=user["display_name"],
        role=user["role"],
        avatar_url=resolve_avatar_url(user.get("avatar_url")),
        bio=user.get("bio"),
        affiliation=user.get("affiliation"),
        orcid=user.get("orcid"),
        created_at=(
            user["created_at"].isoformat()
            if hasattr(user["created_at"], "isoformat")
            else user["created_at"]
        ),
    )


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
        preferred_language=user.get("preferred_language", "en"),
        is_banned=user.get("is_banned", False),
        ban_reason=user.get("ban_reason"),
    )
