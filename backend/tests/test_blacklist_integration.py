"""Tests for blacklist integration — block filtering across repos and services."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Helpers ──────────────────────────────────────────────────────────────────

_VIEWER_ID = str(uuid.uuid4())
_BLOCKED_USER_ID = str(uuid.uuid4())
_BLOCKED_UUID = uuid.UUID(_BLOCKED_USER_ID)
_VIEWER_UUID = uuid.UUID(_VIEWER_ID)


def _mock_redis_with_blocks(viewer_id: str = _VIEWER_ID, blocked: set | None = None):
    """Return a mock Redis whose smembers returns the given blocked set."""
    redis = AsyncMock()
    redis.smembers = AsyncMock(return_value=blocked or {_BLOCKED_USER_ID})
    return redis


# ── Post Repo Tests ──────────────────────────────────────────────────────────


class TestPostRepoExclusion:
    """Verify that exclude_user_ids is wired into SQL for post listing/search."""

    @patch("app.repositories.post_repo.get_pool")
    async def test_find_many_excludes_blocked_users(self, mock_get_pool):
        from app.repositories import post_repo

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=0)
        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm
        mock_get_pool.return_value = mock_pool

        result = await post_repo.find_many(page=1, page_size=20, exclude_user_ids=[_BLOCKED_UUID])

        assert result["posts"] == []
        # Verify the SQL query included the exclusion parameter
        call_args = mock_conn.fetch.call_args
        query = call_args[0][0]
        assert "!= ALL(" in query
        assert "uuid[]" in query

    @patch("app.repositories.post_repo.get_pool")
    async def test_find_many_no_exclusion_when_empty(self, mock_get_pool):
        from app.repositories import post_repo

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=0)
        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm
        mock_get_pool.return_value = mock_pool

        result = await post_repo.find_many(page=1, page_size=20, exclude_user_ids=None)

        assert result["posts"] == []
        call_args = mock_conn.fetch.call_args
        query = call_args[0][0]
        assert "!= ALL(" not in query

    @patch("app.repositories.post_repo.get_pool")
    async def test_search_excludes_blocked_users(self, mock_get_pool):
        from app.repositories import post_repo

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=0)
        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm
        mock_get_pool.return_value = mock_pool

        result, total, total_pages = await post_repo.search(
            keyword="test", exclude_user_ids=[_BLOCKED_UUID]
        )

        call_args = mock_conn.fetch.call_args
        query = call_args[0][0]
        assert "!= ALL(" in query


# ── Comment Repo Tests ───────────────────────────────────────────────────────


class TestCommentRepoExclusion:
    @patch("app.repositories.comment_repo.get_pool")
    async def test_find_many_excludes_blocked_users(self, mock_get_pool):
        from app.repositories import comment_repo

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=0)
        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm
        mock_get_pool.return_value = mock_pool

        post_id = uuid.uuid4()
        result, total = await comment_repo.find_many(post_id, exclude_user_ids=[_BLOCKED_UUID])

        call_args = mock_conn.fetch.call_args
        query = call_args[0][0]
        assert "cm.user_id != ALL(" in query


# ── Notification Repo Tests ──────────────────────────────────────────────────


class TestNotificationRepoExclusion:
    @patch("app.repositories.notification_repo.get_pool")
    async def test_find_many_excludes_blocked_trigger_users(self, mock_get_pool):
        from app.repositories import notification_repo

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=0)
        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm
        mock_get_pool.return_value = mock_pool

        result, total, unread = await notification_repo.find_many(
            _VIEWER_UUID, exclude_user_ids=[_BLOCKED_UUID]
        )

        call_args = mock_conn.fetch.call_args
        query = call_args[0][0]
        assert "trigger_user_id" in query
        assert "!= ALL(" in query


# ── Post Service Tests ───────────────────────────────────────────────────────


class TestPostServiceBlockFiltering:
    @patch("app.services.post.get_pool", return_value=MagicMock())
    @patch("app.services.post.get_redis")
    @patch("app.services.post.post_repo")
    async def test_get_post_by_id_returns_none_for_blocked_author(
        self, mock_repo, mock_get_redis, mock_get_pool
    ):
        from app.services.post import get_post_by_id

        # Post authored by blocked user
        post_row = {
            "id": uuid.uuid4(),
            "user_id": _BLOCKED_UUID,
            "title": "Test",
            "content": "Content",
            "is_deleted": False,
        }
        mock_repo.find_by_id = AsyncMock(return_value=post_row)
        mock_redis = _mock_redis_with_blocks()
        mock_get_redis.return_value = mock_redis

        result = await get_post_by_id(post_row["id"], viewer_id=_VIEWER_ID)
        assert result is None

    @patch("app.services.post.get_pool", return_value=MagicMock())
    @patch("app.services.post.get_redis")
    @patch("app.services.post.post_repo")
    async def test_get_post_by_id_returns_post_when_not_blocked(
        self, mock_repo, mock_get_redis, mock_get_pool
    ):
        from app.services.post import get_post_by_id

        other_user = str(uuid.uuid4())
        post_row = {
            "id": uuid.uuid4(),
            "user_id": uuid.UUID(other_user),
            "title": "Test",
            "content": "Content",
            "is_deleted": False,
            "author_id": uuid.UUID(other_user),
            "author_username": "testuser",
            "author_display_name": "Test User",
            "author_avatar_url": None,
            "category_name": None,
            "sig_name": None,
        }
        mock_repo.find_by_id = AsyncMock(return_value=post_row)
        mock_redis = _mock_redis_with_blocks()
        mock_get_redis.return_value = mock_redis

        with patch("app.services.post.async_row_to_post", new_callable=AsyncMock) as mock_convert:
            mock_convert.return_value = {"id": str(post_row["id"]), "title": "Test"}
            result = await get_post_by_id(post_row["id"], viewer_id=_VIEWER_ID)
            assert result is not None

    @patch("app.services.post.get_pool", return_value=MagicMock())
    @patch("app.services.post.get_redis")
    @patch("app.services.post.post_repo")
    async def test_list_posts_passes_exclude_ids(self, mock_repo, mock_get_redis, mock_get_pool):
        from app.services.post import list_posts

        mock_redis = _mock_redis_with_blocks()
        mock_get_redis.return_value = mock_redis
        mock_repo.find_many = AsyncMock(
            return_value={
                "posts": [],
                "total": 0,
                "total_pages": 1,
                "next_cursor": None,
                "has_more": False,
            }
        )

        await list_posts(viewer_id=_VIEWER_ID)

        call_args = mock_repo.find_many.call_args
        assert call_args.kwargs["exclude_user_ids"] is not None
        assert _BLOCKED_UUID in call_args.kwargs["exclude_user_ids"]

    @patch("app.services.post.get_pool", return_value=MagicMock())
    @patch("app.services.post.get_redis")
    @patch("app.services.post.post_repo")
    async def test_list_posts_no_exclude_when_no_blocks(
        self, mock_repo, mock_get_redis, mock_get_pool
    ):
        from app.services.post import list_posts

        mock_redis = AsyncMock()
        mock_redis.smembers = AsyncMock(return_value=set())
        mock_get_redis.return_value = mock_redis
        mock_repo.find_many = AsyncMock(
            return_value={
                "posts": [],
                "total": 0,
                "total_pages": 1,
                "next_cursor": None,
                "has_more": False,
            }
        )

        await list_posts(viewer_id=_VIEWER_ID)

        call_args = mock_repo.find_many.call_args
        assert call_args.kwargs["exclude_user_ids"] is None


# ── Comment Service Tests ────────────────────────────────────────────────────


class TestCommentServiceBlockFiltering:
    @patch("app.services.comment.get_redis")
    @patch("app.services.comment.comment_repo")
    async def test_list_comments_passes_exclude_ids(self, mock_repo, mock_get_redis):
        from app.services.comment import list_comments

        mock_redis = _mock_redis_with_blocks()
        mock_get_redis.return_value = mock_redis
        mock_repo.find_many = AsyncMock(return_value=([], 0))

        await list_comments(uuid.uuid4(), viewer_id=_VIEWER_ID)

        call_args = mock_repo.find_many.call_args
        assert call_args.kwargs["exclude_user_ids"] is not None

    @patch("app.repositories.post_repo.find_owner_id", new_callable=AsyncMock)
    @patch("app.services.comment.get_redis")
    async def test_create_comment_blocked_by_post_author(self, mock_get_redis, mock_find_owner):
        from app.services.comment import create_comment

        mock_find_owner.return_value = _BLOCKED_USER_ID
        mock_redis = _mock_redis_with_blocks()
        mock_get_redis.return_value = mock_redis

        with pytest.raises(ValueError, match="Cannot comment on this post"):
            await create_comment(uuid.uuid4(), _VIEWER_ID, "test comment")


# ── Co-Author Service Tests ─────────────────────────────────────────────────


class TestCoAuthorBlockCheck:
    @patch("app.services.co_author.get_redis")
    async def test_invite_blocked_user_raises_error(self, mock_get_redis):
        from app.core.errors import AppError
        from app.services.co_author import invite_co_author

        mock_redis = _mock_redis_with_blocks()
        mock_get_redis.return_value = mock_redis

        with pytest.raises(AppError) as exc_info:
            await invite_co_author(
                post_id=uuid.uuid4(),
                user_id=_VIEWER_ID,
                target_user_id=_BLOCKED_USER_ID,
            )
        assert exc_info.value.status_code == 403


# ── Event Handler Tests ──────────────────────────────────────────────────────


class TestEventHandlerBlockCheck:
    async def test_is_blocked_returns_true_for_blocked_pair(self):
        from app.event_handlers import _is_blocked

        with (
            patch("app.core.redis.get_redis") as mock_get_redis,
            patch("app.core.database.get_pool", return_value=MagicMock()),
            patch(
                "app.core.blacklist.get_blocked_user_ids", new_callable=AsyncMock
            ) as mock_get_blocked,
        ):
            mock_get_redis.return_value = AsyncMock()
            mock_get_blocked.return_value = {_BLOCKED_USER_ID}

            result = await _is_blocked(_VIEWER_ID, _BLOCKED_USER_ID)
            assert result is True

    async def test_is_blocked_returns_false_when_not_blocked(self):
        from app.event_handlers import _is_blocked

        with (
            patch("app.core.redis.get_redis") as mock_get_redis,
            patch(
                "app.core.blacklist.get_blocked_user_ids", new_callable=AsyncMock
            ) as mock_get_blocked,
        ):
            mock_get_redis.return_value = AsyncMock()
            mock_get_blocked.return_value = set()

            other_user = str(uuid.uuid4())
            result = await _is_blocked(_VIEWER_ID, other_user)
            assert result is False

    async def test_is_blocked_returns_false_on_redis_error(self):
        from app.event_handlers import _is_blocked

        with patch("app.core.redis.get_redis") as mock_get_redis:
            mock_get_redis.side_effect = RuntimeError("Redis down")

            result = await _is_blocked(_VIEWER_ID, _BLOCKED_USER_ID)
            assert result is False


# ── Album Comment Service Tests ──────────────────────────────────────────────


class TestAlbumCommentBlockFiltering:
    @patch("app.services.album.get_redis")
    @patch("app.services.album.album_repo")
    @patch("app.services.album.get_pool")
    async def test_list_comments_passes_exclude_ids(self, mock_get_pool, mock_repo, mock_get_redis):
        from app.services.album import list_comments

        mock_redis = _mock_redis_with_blocks()
        mock_get_redis.return_value = mock_redis

        mock_conn = AsyncMock()
        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm
        mock_get_pool.return_value = mock_pool

        mock_repo.find_album_by_id = AsyncMock(return_value={"id": uuid.uuid4(), "title": "T"})
        mock_repo.find_comments = AsyncMock(return_value=([], 0))

        await list_comments(str(uuid.uuid4()), viewer_id=_VIEWER_ID)

        call_args = mock_repo.find_comments.call_args
        assert call_args.kwargs["exclude_user_ids"] is not None


# ── User Profile Block Check Tests ───────────────────────────────────────────


class TestUserProfileBlockCheck:
    async def test_blocked_user_profile_returns_404(self, client, auth_headers):
        """GET /users/{id} returns 404 when viewer has blocked that user."""
        target_user_id = uuid.uuid4()
        headers, viewer_id, _ = auth_headers("MEMBER", _VIEWER_ID)

        mock_user = {
            "id": target_user_id,
            "username": "blocked_user",
            "display_name": "Blocked",
            "avatar_url": None,
            "bio": None,
            "affiliation": None,
            "orcid": None,
            "is_deleted": False,
            "is_banned": False,
            "created_at": "2025-01-01T00:00:00Z",
        }

        # Mock the viewer's own user record for deps.get_current_user lookup
        viewer_user = {
            "id": uuid.UUID(_VIEWER_ID),
            "username": "viewer",
            "display_name": "Viewer",
            "avatar_url": None,
            "bio": None,
            "affiliation": None,
            "orcid": None,
            "is_deleted": False,
            "is_banned": False,
        }

        async def _mock_get_user(uid: uuid.UUID) -> dict | None:
            if uid == target_user_id:
                return mock_user
            if str(uid) == _VIEWER_ID:
                return viewer_user
            return None

        with (
            patch(
                "app.api.v1.endpoints.users.get_user_by_id",
                new_callable=AsyncMock,
                side_effect=_mock_get_user,
            ),
            patch(
                "app.core.deps.get_user_by_id", new_callable=AsyncMock, side_effect=_mock_get_user
            ),
            patch("app.core.redis.get_redis") as mock_redis_fn,
            patch(
                "app.core.blacklist.get_blocked_user_ids", new_callable=AsyncMock
            ) as mock_get_blocked,
            patch("app.core.deps.validate_session", new_callable=AsyncMock, return_value=True),
        ):
            mock_redis_fn.return_value = AsyncMock()
            mock_get_blocked.return_value = {str(target_user_id)}

            resp = await client.get(f"/api/v1/users/{target_user_id}", headers=headers)
            assert resp.status_code == 404


# ── Form Response Block Check Tests ──────────────────────────────────────────


class TestFormResponseBlockFiltering:
    @patch("app.services.form.get_redis")
    @patch("app.services.form.form_repo")
    async def test_list_form_responses_passes_exclude_ids(self, mock_repo, mock_get_redis):
        from app.services.form import list_form_responses

        mock_redis = _mock_redis_with_blocks()
        mock_get_redis.return_value = mock_redis
        mock_repo.find_responses = AsyncMock(return_value=([], 0))

        await list_form_responses(uuid.uuid4(), viewer_id=_VIEWER_ID)

        call_args = mock_repo.find_responses.call_args
        assert call_args.kwargs["exclude_user_ids"] is not None

    @patch("app.services.form.get_redis")
    @patch("app.services.form.form_repo")
    async def test_submit_response_to_blocked_creator_raises(self, mock_repo, mock_get_redis):
        from app.services.form import submit_response

        mock_redis = _mock_redis_with_blocks()
        mock_get_redis.return_value = mock_redis

        # Form created by blocked user
        mock_repo.find_by_id = AsyncMock(
            return_value=({"created_by": _BLOCKED_UUID, "sig_id": None}, 0)
        )

        with pytest.raises(ValueError, match="Cannot submit this form"):
            await submit_response(uuid.uuid4(), _VIEWER_ID, {"q1": "answer"})
