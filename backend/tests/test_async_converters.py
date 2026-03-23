"""Tests for async converter functions and their integration with services.

Validates that:
1. Each async converter returns the correct structure
2. async_resolve_avatar_url is called (not the sync version)
3. asyncio.gather batch conversion works correctly
4. Sync converters still work (backward compatibility)
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Mock path constants — patch where the name is looked up, not where defined
# ---------------------------------------------------------------------------

# shared.py imports async_resolve_avatar_url from user_converter at module level
_SHARED_ASYNC_RESOLVE = "app.converters.shared.async_resolve_avatar_url"

# notification_converter.py imports async_resolve_avatar_url from user_converter
_NOTIF_ASYNC_RESOLVE = "app.converters.notification_converter.async_resolve_avatar_url"

# sig_converter.py imports async_resolve_avatar_url from user_converter
_SIG_ASYNC_RESOLVE = "app.converters.sig_converter.async_resolve_avatar_url"

# user_converter.py defines async_resolve_avatar_url in its own module
_USER_ASYNC_RESOLVE = "app.converters.user_converter.async_resolve_avatar_url"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc).replace(microsecond=0)
_YESTERDAY = _NOW - timedelta(days=1)


def _uid() -> uuid.UUID:
    return uuid.uuid4()


def _uid_str() -> str:
    return str(uuid.uuid4())


def _make_post_row(**overrides) -> dict:
    row = {
        "id": _uid(),
        "title": "Async Post",
        "content": "<p>Body</p>",
        "author_id": _uid(),
        "author_username": "author1",
        "author_display_name": "Author One",
        "author_avatar_url": "avatars/author.png",
        "category_id": _uid(),
        "category_name": "General",
        "sig_id": None,
        "sig_name": None,
        "keywords": ["async", "python"],
        "allow_comments": True,
        "version": 1,
        "comment_count": 3,
        "is_pinned": False,
        "view_count": 10,
        "last_comment_at": _NOW,
        "reactions": None,
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    row.update(overrides)
    return row


def _make_comment_row(**overrides) -> dict:
    row = {
        "id": _uid(),
        "post_id": _uid(),
        "content": "<p>A comment</p>",
        "author_id": _uid(),
        "author_username": "commenter",
        "author_display_name": "Commenter",
        "author_avatar_url": "avatars/commenter.png",
        "parent_id": None,
        "mentions": None,
        "reactions": None,
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    row.update(overrides)
    return row


def _make_notification_row(**overrides) -> dict:
    row = {
        "id": _uid(),
        "action_type": "COMMENT",
        "entity_type": "post",
        "entity_id": _uid(),
        "message": "Someone commented",
        "is_read": False,
        "created_at": _NOW,
        "trigger_user_id": _uid(),
        "trigger_display_name": "Trigger User",
        "trigger_avatar_url": "avatars/trigger.png",
    }
    row.update(overrides)
    return row


def _make_member_row(**overrides) -> dict:
    row = {
        "id": _uid(),
        "sig_id": _uid(),
        "user_id": _uid(),
        "role": "MEMBER",
        "display_name": "Member One",
        "username": "member1",
        "avatar_url": "avatars/member.png",
        "created_at": _NOW,
    }
    row.update(overrides)
    return row


def _make_user_dict(**overrides) -> dict:
    user = {
        "id": _uid(),
        "username": "testuser",
        "display_name": "Test User",
        "role": "MEMBER",
        "avatar_url": "avatars/test.png",
        "bio": "A researcher",
        "affiliation": "MIT",
        "orcid": "0000-0001-2345-6789",
        "preferred_language": "en",
        "is_banned": False,
        "ban_reason": None,
        "created_at": _NOW,
    }
    user.update(overrides)
    return user


# =========================================================================
# async_resolve_avatar_url
# =========================================================================


class TestAsyncResolveAvatarUrl:
    """Tests for the async version of resolve_avatar_url."""

    @pytest.mark.asyncio
    async def test_none_returns_none(self):
        from app.converters.user_converter import async_resolve_avatar_url

        result = await async_resolve_avatar_url(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_string_returns_none(self):
        from app.converters.user_converter import async_resolve_avatar_url

        result = await async_resolve_avatar_url("")
        assert result is None

    @pytest.mark.asyncio
    async def test_http_url_passthrough(self):
        from app.converters.user_converter import async_resolve_avatar_url

        url = "http://example.com/avatar.jpg"
        result = await async_resolve_avatar_url(url)
        assert result == url

    @pytest.mark.asyncio
    async def test_https_url_passthrough(self):
        from app.converters.user_converter import async_resolve_avatar_url

        url = "https://cdn.example.com/avatar.jpg"
        result = await async_resolve_avatar_url(url)
        assert result == url

    @pytest.mark.asyncio
    async def test_minio_key_calls_async_storage(self):
        from app.converters.user_converter import async_resolve_avatar_url

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)  # cache miss
        mock_redis.setex = AsyncMock()

        with (
            patch("app.core.redis.get_redis", return_value=mock_redis),
            patch(
                "app.core.async_storage.generate_presigned_url",
                new_callable=AsyncMock,
                return_value="https://minio/signed-async",
            ) as mock_presign,
        ):
            result = await async_resolve_avatar_url("avatars/user123.png")
            assert result == "https://minio/signed-async"
            mock_presign.assert_called_once_with("avatars/user123.png", expires_in=3600)
            mock_redis.setex.assert_called_once_with(
                "presigned:avatars/user123.png", 2700, "https://minio/signed-async"
            )

    @pytest.mark.asyncio
    async def test_exception_returns_raw_key(self):
        from app.converters.user_converter import async_resolve_avatar_url

        with patch(
            "app.core.async_storage.generate_presigned_url",
            new_callable=AsyncMock,
            side_effect=Exception("Storage down"),
        ):
            result = await async_resolve_avatar_url("avatars/broken.png")
            assert result == "avatars/broken.png"


# =========================================================================
# async_build_author
# =========================================================================


class TestAsyncBuildAuthor:
    """Tests for the async version of build_author."""

    @pytest.mark.asyncio
    async def test_builds_correct_structure(self):
        from app.converters.shared import async_build_author

        with patch(
            _SHARED_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value="https://cdn/avatar.jpg",
        ):
            row = {
                "author_id": _uid(),
                "author_username": "user1",
                "author_display_name": "User One",
                "author_avatar_url": "avatars/user1.png",
            }
            result = await async_build_author(row)

            assert result["id"] == str(row["author_id"])
            assert result["username"] == "user1"
            assert result["display_name"] == "User One"
            assert result["avatar_url"] == "https://cdn/avatar.jpg"

    @pytest.mark.asyncio
    async def test_calls_async_resolve(self):
        """Verify async_resolve_avatar_url is called, not the sync version."""
        from app.converters.shared import async_build_author

        with patch(
            _SHARED_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_async:
            row = {
                "author_id": _uid(),
                "author_username": "u",
                "author_display_name": "U",
                "author_avatar_url": None,
            }
            await async_build_author(row)
            mock_async.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_null_avatar(self):
        from app.converters.shared import async_build_author

        with patch(
            _SHARED_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value=None,
        ):
            row = {
                "author_id": _uid(),
                "author_username": "noavatar",
                "author_display_name": "No Avatar",
                "author_avatar_url": None,
            }
            result = await async_build_author(row)
            assert result["avatar_url"] is None


# =========================================================================
# async_row_to_post
# =========================================================================


class TestAsyncRowToPost:
    """Tests for the async version of row_to_post."""

    @pytest.mark.asyncio
    async def test_returns_correct_structure(self):
        from app.converters.post_converter import async_row_to_post

        with patch(
            _SHARED_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value="https://cdn/author.jpg",
        ):
            row = _make_post_row()
            result = await async_row_to_post(row)

            assert result["id"] == str(row["id"])
            assert result["title"] == "Async Post"
            assert result["content"] == "<p>Body</p>"
            assert result["author"]["id"] == str(row["author_id"])
            assert result["author"]["avatar_url"] == "https://cdn/author.jpg"
            assert result["category_id"] == str(row["category_id"])
            assert result["keywords"] == ["async", "python"]
            assert result["allow_comments"] is True
            assert result["version"] == 1
            assert result["comment_count"] == 3
            assert result["is_pinned"] is False
            assert result["view_count"] == 10
            assert result["created_at"] == _NOW.isoformat()

    @pytest.mark.asyncio
    async def test_null_optional_fields(self):
        from app.converters.post_converter import async_row_to_post

        with patch(
            _SHARED_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value=None,
        ):
            row = _make_post_row(
                author_avatar_url=None,
                category_id=None,
                sig_id=None,
                keywords=None,
                last_comment_at=None,
            )
            result = await async_row_to_post(row)

            assert result["author"]["avatar_url"] is None
            assert result["category_id"] is None
            assert result["sig_id"] is None
            assert result["keywords"] is None
            assert result["last_comment_at"] is None

    @pytest.mark.asyncio
    async def test_reactions_json_string_parsed(self):
        from app.converters.post_converter import async_row_to_post

        with patch(
            _SHARED_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value=None,
        ):
            row = _make_post_row(reactions='{"like": ["u1", "u2", "u3", "u4", "u5"]}')
            result = await async_row_to_post(row)
            assert result["reaction_counts"] == {"like": 5}
            assert result["user_reactions"] is None
            assert result["_raw_reactions"] == {"like": ["u1", "u2", "u3", "u4", "u5"]}


# =========================================================================
# async_row_to_comment
# =========================================================================


class TestAsyncRowToComment:
    """Tests for the async version of row_to_comment."""

    @pytest.mark.asyncio
    async def test_returns_correct_structure(self):
        from app.converters.comment_converter import async_row_to_comment

        with patch(
            _SHARED_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value="https://cdn/commenter.jpg",
        ):
            row = _make_comment_row()
            result = await async_row_to_comment(row)

            assert result["id"] == str(row["id"])
            assert result["post_id"] == str(row["post_id"])
            assert result["content"] == "<p>A comment</p>"
            assert result["author"]["id"] == str(row["author_id"])
            assert result["author"]["avatar_url"] == "https://cdn/commenter.jpg"
            assert result["parent_id"] is None
            assert result["created_at"] == _NOW.isoformat()

    @pytest.mark.asyncio
    async def test_with_parent_and_mentions(self):
        from app.converters.comment_converter import async_row_to_comment

        parent_id = _uid()
        with patch(
            _SHARED_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value=None,
        ):
            row = _make_comment_row(
                parent_id=parent_id,
                mentions=["user1", "user2"],
                reactions={"thumbsup": ["u1"]},
            )
            result = await async_row_to_comment(row)

            assert result["parent_id"] == str(parent_id)
            assert result["mentions"] == ["user1", "user2"]
            assert result["reaction_counts"] == {"thumbsup": 1}
            assert result["user_reactions"] is None

    @pytest.mark.asyncio
    async def test_reactions_json_string(self):
        from app.converters.comment_converter import async_row_to_comment

        with patch(
            _SHARED_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value=None,
        ):
            row = _make_comment_row(reactions='{"heart": ["u1", "u2"]}')
            result = await async_row_to_comment(row)
            assert result["reaction_counts"] == {"heart": 2}
            assert result["user_reactions"] is None


# =========================================================================
# async_row_to_notification
# =========================================================================


class TestAsyncRowToNotification:
    """Tests for the async version of row_to_notification."""

    @pytest.mark.asyncio
    async def test_with_trigger_user(self):
        from app.converters.notification_converter import async_row_to_notification

        with patch(
            _NOTIF_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value="https://cdn/trigger.jpg",
        ):
            row = _make_notification_row()
            result = await async_row_to_notification(row)

            assert result["id"] == str(row["id"])
            assert result["action_type"] == "COMMENT"
            assert result["entity_type"] == "post"
            assert result["message"] == "Someone commented"
            assert result["is_read"] is False
            assert result["trigger_user"] is not None
            assert result["trigger_user"]["id"] == str(row["trigger_user_id"])
            assert result["trigger_user"]["display_name"] == "Trigger User"
            assert result["trigger_user"]["avatar_url"] == "https://cdn/trigger.jpg"

    @pytest.mark.asyncio
    async def test_without_trigger_user(self):
        from app.converters.notification_converter import async_row_to_notification

        row = _make_notification_row(
            trigger_user_id=None,
            trigger_display_name=None,
            trigger_avatar_url=None,
        )
        result = await async_row_to_notification(row)
        assert result["trigger_user"] is None

    @pytest.mark.asyncio
    async def test_trigger_user_id_without_display_name(self):
        from app.converters.notification_converter import async_row_to_notification

        row = _make_notification_row(trigger_display_name=None)
        result = await async_row_to_notification(row)
        assert result["trigger_user"] is None

    @pytest.mark.asyncio
    async def test_entity_id_none(self):
        from app.converters.notification_converter import async_row_to_notification

        with patch(
            _NOTIF_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value=None,
        ):
            row = _make_notification_row(entity_id=None)
            result = await async_row_to_notification(row)
            assert result["entity_id"] is None


# =========================================================================
# async_row_to_member
# =========================================================================


class TestAsyncRowToMember:
    """Tests for the async version of row_to_member."""

    @pytest.mark.asyncio
    async def test_returns_correct_structure(self):
        from app.converters.sig_converter import async_row_to_member

        with patch(
            _SIG_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value="https://cdn/member.jpg",
        ):
            row = _make_member_row()
            result = await async_row_to_member(row)

            assert result["id"] == str(row["id"])
            assert result["sig_id"] == str(row["sig_id"])
            assert result["user_id"] == str(row["user_id"])
            assert result["role"] == "MEMBER"
            assert result["display_name"] == "Member One"
            assert result["username"] == "member1"
            assert result["avatar_url"] == "https://cdn/member.jpg"
            assert result["created_at"] == _NOW.isoformat()

    @pytest.mark.asyncio
    async def test_null_avatar(self):
        from app.converters.sig_converter import async_row_to_member

        with patch(
            _SIG_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value=None,
        ):
            row = _make_member_row(avatar_url=None)
            result = await async_row_to_member(row)
            assert result["avatar_url"] is None

    @pytest.mark.asyncio
    async def test_admin_role(self):
        from app.converters.sig_converter import async_row_to_member

        with patch(
            _SIG_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value=None,
        ):
            row = _make_member_row(role="ADMIN")
            result = await async_row_to_member(row)
            assert result["role"] == "ADMIN"


# =========================================================================
# async_user_to_response and async_user_to_public_response
# =========================================================================


class TestAsyncUserToResponse:
    """Tests for async_user_to_response."""

    @pytest.mark.asyncio
    async def test_returns_correct_pydantic_model(self):
        from app.converters.user_converter import async_user_to_response
        from app.schemas.user import UserResponse

        with patch(
            _USER_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value="https://cdn/test.jpg",
        ):
            user = _make_user_dict()
            result = await async_user_to_response(user)

            assert isinstance(result, UserResponse)
            assert result.id == str(user["id"])
            assert result.username == "testuser"
            assert result.display_name == "Test User"
            assert result.role == "MEMBER"
            assert result.avatar_url == "https://cdn/test.jpg"
            assert result.bio == "A researcher"
            assert result.affiliation == "MIT"
            assert result.orcid == "0000-0001-2345-6789"
            assert result.preferred_language == "en"
            assert result.is_banned is False
            assert result.ban_reason is None

    @pytest.mark.asyncio
    async def test_banned_user(self):
        from app.converters.user_converter import async_user_to_response

        with patch(
            _USER_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value=None,
        ):
            user = _make_user_dict(is_banned=True, ban_reason="Spam")
            result = await async_user_to_response(user)
            assert result.is_banned is True
            assert result.ban_reason == "Spam"

    @pytest.mark.asyncio
    async def test_preferred_language_default(self):
        from app.converters.user_converter import async_user_to_response

        with patch(
            _USER_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value=None,
        ):
            user = _make_user_dict()
            del user["preferred_language"]
            result = await async_user_to_response(user)
            assert result.preferred_language == "en"


class TestAsyncUserToPublicResponse:
    """Tests for async_user_to_public_response."""

    @pytest.mark.asyncio
    async def test_returns_correct_pydantic_model(self):
        from app.converters.user_converter import async_user_to_public_response
        from app.schemas.user import PublicUserResponse

        with patch(
            _USER_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value="https://cdn/pub.jpg",
        ):
            user = _make_user_dict()
            result = await async_user_to_public_response(user)

            assert isinstance(result, PublicUserResponse)
            assert result.id == str(user["id"])
            assert result.username == "testuser"
            assert result.display_name == "Test User"
            assert result.role == "MEMBER"
            assert result.avatar_url == "https://cdn/pub.jpg"
            assert result.bio == "A researcher"
            assert result.affiliation == "MIT"
            assert result.orcid == "0000-0001-2345-6789"
            assert result.created_at == _NOW.isoformat()

    @pytest.mark.asyncio
    async def test_created_at_string(self):
        from app.converters.user_converter import async_user_to_public_response

        with patch(
            _USER_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value=None,
        ):
            user = _make_user_dict(created_at="2026-01-01T00:00:00+00:00")
            result = await async_user_to_public_response(user)
            assert result.created_at == "2026-01-01T00:00:00+00:00"

    @pytest.mark.asyncio
    async def test_null_optional_fields(self):
        from app.converters.user_converter import async_user_to_public_response

        with patch(
            _USER_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value=None,
        ):
            user = _make_user_dict(avatar_url=None, bio=None, affiliation=None, orcid=None)
            result = await async_user_to_public_response(user)
            assert result.avatar_url is None
            assert result.bio is None
            assert result.affiliation is None
            assert result.orcid is None


# =========================================================================
# asyncio.gather batch conversion
# =========================================================================


class TestBatchConversion:
    """Test that asyncio.gather works correctly for batch conversions."""

    @pytest.mark.asyncio
    async def test_gather_multiple_posts(self):
        from app.converters.post_converter import async_row_to_post

        with patch(
            _SHARED_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value="https://cdn/avatar.jpg",
        ):
            rows = [_make_post_row(title=f"Post {i}") for i in range(5)]
            results = list(await asyncio.gather(*[async_row_to_post(r) for r in rows]))

            assert len(results) == 5
            for i, result in enumerate(results):
                assert result["title"] == f"Post {i}"
                assert result["author"]["avatar_url"] == "https://cdn/avatar.jpg"

    @pytest.mark.asyncio
    async def test_gather_multiple_comments(self):
        from app.converters.comment_converter import async_row_to_comment

        with patch(
            _SHARED_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value=None,
        ):
            rows = [_make_comment_row(content=f"<p>Comment {i}</p>") for i in range(3)]
            results = list(await asyncio.gather(*[async_row_to_comment(r) for r in rows]))

            assert len(results) == 3
            for i, result in enumerate(results):
                assert result["content"] == f"<p>Comment {i}</p>"

    @pytest.mark.asyncio
    async def test_gather_multiple_notifications(self):
        from app.converters.notification_converter import async_row_to_notification

        with patch(
            _NOTIF_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value="https://cdn/trig.jpg",
        ):
            rows = [_make_notification_row(message=f"Notif {i}") for i in range(4)]
            results = list(await asyncio.gather(*[async_row_to_notification(r) for r in rows]))

            assert len(results) == 4
            for i, result in enumerate(results):
                assert result["message"] == f"Notif {i}"

    @pytest.mark.asyncio
    async def test_gather_multiple_members(self):
        from app.converters.sig_converter import async_row_to_member

        with patch(
            _SIG_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value="https://cdn/m.jpg",
        ):
            rows = [_make_member_row(username=f"member{i}") for i in range(3)]
            results = list(await asyncio.gather(*[async_row_to_member(r) for r in rows]))

            assert len(results) == 3
            for i, result in enumerate(results):
                assert result["username"] == f"member{i}"

    @pytest.mark.asyncio
    async def test_gather_empty_list(self):
        """asyncio.gather with empty list returns empty tuple."""
        from app.converters.post_converter import async_row_to_post

        results = list(await asyncio.gather(*[async_row_to_post(r) for r in []]))
        assert results == []

    @pytest.mark.asyncio
    async def test_gather_preserves_order(self):
        """Verify asyncio.gather preserves insertion order."""
        from app.converters.post_converter import async_row_to_post

        with patch(
            _SHARED_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value=None,
        ):
            titles = ["First", "Second", "Third", "Fourth", "Fifth"]
            rows = [_make_post_row(title=t) for t in titles]
            results = list(await asyncio.gather(*[async_row_to_post(r) for r in rows]))

            result_titles = [r["title"] for r in results]
            assert result_titles == titles


# =========================================================================
# Sync backward compatibility
# =========================================================================


class TestSyncBackwardCompatibility:
    """Verify that sync converter functions still work correctly."""

    @patch(
        "app.core.storage.generate_presigned_url",
        return_value="https://cdn/sync.jpg",
    )
    def test_sync_resolve_avatar_url(self, mock_presign):
        from app.converters.user_converter import resolve_avatar_url

        result = resolve_avatar_url("avatars/test.png")
        assert result == "https://cdn/sync.jpg"
        mock_presign.assert_called_once_with("avatars/test.png", expires_in=3600)

    def test_sync_resolve_avatar_url_none(self):
        from app.converters.user_converter import resolve_avatar_url

        assert resolve_avatar_url(None) is None

    def test_sync_resolve_avatar_url_http(self):
        from app.converters.user_converter import resolve_avatar_url

        url = "https://example.com/pic.jpg"
        assert resolve_avatar_url(url) == url

    @patch(
        "app.core.storage.generate_presigned_url",
        return_value="https://cdn/sync.jpg",
    )
    def test_sync_build_author(self, mock_presign):
        from app.converters.shared import build_author

        row = {
            "author_id": _uid(),
            "author_username": "user1",
            "author_display_name": "User One",
            "author_avatar_url": "avatars/user1.png",
        }
        result = build_author(row)
        assert result["id"] == str(row["author_id"])
        assert result["username"] == "user1"
        assert result["avatar_url"] == "https://cdn/sync.jpg"

    @patch(
        "app.core.storage.generate_presigned_url",
        return_value="https://cdn/sync.jpg",
    )
    def test_sync_row_to_post(self, mock_presign):
        from app.converters.post_converter import row_to_post

        row = _make_post_row()
        result = row_to_post(row)
        assert result["id"] == str(row["id"])
        assert result["title"] == "Async Post"
        assert result["author"]["avatar_url"] == "https://cdn/sync.jpg"

    @patch(
        "app.core.storage.generate_presigned_url",
        return_value="https://cdn/sync.jpg",
    )
    def test_sync_row_to_comment(self, mock_presign):
        from app.converters.comment_converter import row_to_comment

        row = _make_comment_row()
        result = row_to_comment(row)
        assert result["id"] == str(row["id"])
        assert result["author"]["avatar_url"] == "https://cdn/sync.jpg"

    @patch(
        "app.core.storage.generate_presigned_url",
        return_value="https://cdn/sync.jpg",
    )
    def test_sync_row_to_notification(self, mock_presign):
        from app.converters.notification_converter import row_to_notification

        row = _make_notification_row()
        result = row_to_notification(row)
        assert result["trigger_user"]["avatar_url"] == "https://cdn/sync.jpg"

    @patch(
        "app.core.storage.generate_presigned_url",
        return_value="https://cdn/sync.jpg",
    )
    def test_sync_row_to_member(self, mock_presign):
        from app.converters.sig_converter import row_to_member

        row = _make_member_row()
        result = row_to_member(row)
        assert result["avatar_url"] == "https://cdn/sync.jpg"

    @patch(
        "app.core.storage.generate_presigned_url",
        return_value="https://cdn/sync.jpg",
    )
    def test_sync_user_to_response(self, mock_presign):
        from app.converters.user_converter import user_to_response
        from app.schemas.user import UserResponse

        user = _make_user_dict()
        result = user_to_response(user)
        assert isinstance(result, UserResponse)
        assert result.avatar_url == "https://cdn/sync.jpg"

    @patch(
        "app.core.storage.generate_presigned_url",
        return_value="https://cdn/sync.jpg",
    )
    def test_sync_user_to_public_response(self, mock_presign):
        from app.converters.user_converter import user_to_public_response
        from app.schemas.user import PublicUserResponse

        user = _make_user_dict()
        result = user_to_public_response(user)
        assert isinstance(result, PublicUserResponse)
        assert result.avatar_url == "https://cdn/sync.jpg"


# =========================================================================
# Async converters use async_resolve (not sync resolve)
# =========================================================================


class TestAsyncConvertersUseAsyncResolve:
    """Verify that async converters call async_resolve_avatar_url, not the sync one."""

    @pytest.mark.asyncio
    async def test_async_row_to_post_uses_async_resolve(self):
        from app.converters.post_converter import async_row_to_post

        with patch(
            _SHARED_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value="https://async/avatar.jpg",
        ) as mock_async:
            row = _make_post_row()
            result = await async_row_to_post(row)
            mock_async.assert_called_once_with("avatars/author.png")
            assert result["author"]["avatar_url"] == "https://async/avatar.jpg"

    @pytest.mark.asyncio
    async def test_async_row_to_comment_uses_async_resolve(self):
        from app.converters.comment_converter import async_row_to_comment

        with patch(
            _SHARED_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value="https://async/commenter.jpg",
        ) as mock_async:
            row = _make_comment_row()
            result = await async_row_to_comment(row)
            mock_async.assert_called_once_with("avatars/commenter.png")
            assert result["author"]["avatar_url"] == "https://async/commenter.jpg"

    @pytest.mark.asyncio
    async def test_async_row_to_notification_uses_async_resolve(self):
        from app.converters.notification_converter import async_row_to_notification

        with patch(
            _NOTIF_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value="https://async/trigger.jpg",
        ) as mock_async:
            row = _make_notification_row()
            result = await async_row_to_notification(row)
            mock_async.assert_called_once_with("avatars/trigger.png")
            assert result["trigger_user"]["avatar_url"] == "https://async/trigger.jpg"

    @pytest.mark.asyncio
    async def test_async_row_to_member_uses_async_resolve(self):
        from app.converters.sig_converter import async_row_to_member

        with patch(
            _SIG_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value="https://async/member.jpg",
        ) as mock_async:
            row = _make_member_row()
            result = await async_row_to_member(row)
            mock_async.assert_called_once_with("avatars/member.png")
            assert result["avatar_url"] == "https://async/member.jpg"

    @pytest.mark.asyncio
    async def test_async_user_to_response_uses_async_resolve(self):
        from app.converters.user_converter import async_user_to_response

        with patch(
            _USER_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value="https://async/user.jpg",
        ) as mock_async:
            user = _make_user_dict()
            result = await async_user_to_response(user)
            mock_async.assert_called_once_with("avatars/test.png")
            assert result.avatar_url == "https://async/user.jpg"

    @pytest.mark.asyncio
    async def test_async_user_to_public_response_uses_async_resolve(self):
        from app.converters.user_converter import async_user_to_public_response

        with patch(
            _USER_ASYNC_RESOLVE,
            new_callable=AsyncMock,
            return_value="https://async/pub.jpg",
        ) as mock_async:
            user = _make_user_dict()
            result = await async_user_to_public_response(user)
            mock_async.assert_called_once_with("avatars/test.png")
            assert result.avatar_url == "https://async/pub.jpg"
