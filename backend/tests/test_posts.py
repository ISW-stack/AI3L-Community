"""Tests for app.services.post — create, rate limit, version conflict, delete."""

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest


def _make_post_row(user_id=None, version=1, is_pinned=False, view_count=0, like_count=0):
    """Helper to create a mock post row dict with joined author/category fields."""
    uid = uuid.uuid4() if user_id is None else uuid.UUID(user_id)
    now = datetime.now(timezone.utc)
    return {
        "id": uuid.uuid4(),
        "title": "Test Post",
        "content": "<p>Hello</p>",
        "user_id": uid,
        "category_id": None,
        "sig_id": None,
        "keywords": ["test"],
        "allow_comments": True,
        "version": version,
        "comment_count": 0,
        "like_count": like_count,
        "is_pinned": is_pinned,
        "view_count": view_count,
        "last_comment_at": None,
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
        "author_id": uid,
        "author_username": "alice",
        "author_display_name": "Alice",
        "author_avatar_url": None,
        "category_name": None,
        "search_vector": None,
    }


class TestCreatePost:
    @patch(
        "app.services.post._atomic_check_and_increment_post_limit",
        new_callable=AsyncMock,
        return_value=True,
    )
    @patch("app.repositories.post_repo.get_pool")
    async def test_create_post_success(
        self, mock_get_pool, mock_atomic_limit, mock_pool, mock_conn
    ):
        from app.services.post import create_post

        user_id = str(uuid.uuid4())
        mock_conn.fetchrow.return_value = _make_post_row(user_id=user_id)
        mock_get_pool.return_value = mock_pool

        result = await create_post(user_id, "Title", "Content")
        assert result["title"] == "Test Post"
        mock_atomic_limit.assert_called_once()

    @patch(
        "app.services.post._atomic_check_and_increment_post_limit",
        new_callable=AsyncMock,
        return_value=False,
    )
    async def test_create_post_rate_limited(self, mock_atomic_limit):
        from app.services.post import create_post

        with pytest.raises(ValueError, match="Daily post limit"):
            await create_post(str(uuid.uuid4()), "Title", "Content")

    @patch(
        "app.services.post._atomic_check_and_increment_post_limit",
        new_callable=AsyncMock,
        return_value=True,
    )
    @patch("app.services.post._rollback_daily_post_count", new_callable=AsyncMock)
    @patch("app.repositories.post_repo.get_pool")
    async def test_create_post_fk_violation_raises_value_error(
        self, mock_get_pool, mock_rollback, mock_atomic_limit, mock_pool, mock_conn
    ):
        """ForeignKeyViolationError on insert → ValueError(category not found)."""
        import asyncpg

        from app.services.post import create_post

        mock_conn.fetchrow.side_effect = asyncpg.exceptions.ForeignKeyViolationError()
        mock_get_pool.return_value = mock_pool

        with pytest.raises(ValueError, match="Category not found"):
            await create_post(str(uuid.uuid4()), "Title", "Content", category_id=str(uuid.uuid4()))
        mock_rollback.assert_called_once()

    @patch(
        "app.services.post._atomic_check_and_increment_post_limit",
        new_callable=AsyncMock,
        return_value=True,
    )
    @patch("app.services.post.emit", new_callable=AsyncMock, side_effect=RuntimeError("Redis down"))
    @patch("app.repositories.post_repo.get_pool")
    @patch("app.repositories.sig_repo.get_pool")
    async def test_create_post_emit_failure_does_not_propagate(
        self, mock_sig_pool, mock_get_pool, mock_emit, mock_atomic_limit, mock_pool, mock_conn
    ):
        """If emit raises, create_post still returns the post (fire-and-forget)."""
        from app.services.post import create_post

        user_id = str(uuid.uuid4())
        post_row = _make_post_row(user_id=user_id)
        # First fetchrow: sig_repo.get_member_role returns role; second: post insert
        mock_conn.fetchrow = AsyncMock(side_effect=[{"role": "MEMBER"}, post_row])
        mock_get_pool.return_value = mock_pool
        mock_sig_pool.return_value = mock_pool

        # sig_id triggers emit; should not raise even though emit fails
        result = await create_post(user_id, "Title", "Content", sig_id=str(uuid.uuid4()))
        assert result["title"] == "Test Post"


class TestCreatePostSigMembership:
    """Bug #3: Non-SIG-member should not be able to post in a SIG."""

    @patch(
        "app.services.post._atomic_check_and_increment_post_limit",
        new_callable=AsyncMock,
        return_value=True,
    )
    @patch("app.services.post._rollback_daily_post_count", new_callable=AsyncMock)
    @patch("app.repositories.sig_repo.get_pool")
    async def test_create_post_non_sig_member_raises(
        self, mock_sig_pool, mock_rollback, mock_atomic_limit, mock_pool, mock_conn
    ):
        from app.services.post import create_post

        user_id = str(uuid.uuid4())
        sig_id = str(uuid.uuid4())

        # sig_repo.get_member_role uses fetchrow; returns None → not a member
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_sig_pool.return_value = mock_pool

        with pytest.raises(PermissionError, match="must be a member"):
            await create_post(user_id, "Title", "Content", sig_id=sig_id)
        mock_rollback.assert_called_once()


class TestPostCreateSchema:
    def test_keyword_over_50_chars_rejected(self):
        """Keywords longer than 50 chars must be rejected by Pydantic."""
        from pydantic import ValidationError

        from app.schemas.post import PostCreateRequest

        with pytest.raises(ValidationError, match="50 characters"):
            PostCreateRequest(
                title="Title",
                content="body",
                keywords=["x" * 51],
            )

    def test_keyword_exactly_50_chars_accepted(self):
        """Keywords of exactly 50 chars must be accepted."""
        from app.schemas.post import PostCreateRequest

        req = PostCreateRequest(title="Title", content="body", keywords=["x" * 50])
        assert req.keywords is not None
        assert len(req.keywords[0]) == 50


class TestUpdatePost:
    @patch("app.services.post.get_pool")
    async def test_update_post_version_conflict(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.post import update_post

        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        current_row = _make_post_row(user_id=user_id, version=3)
        mock_conn.fetchrow.return_value = current_row
        mock_get_pool.return_value = mock_pool

        with pytest.raises(ValueError, match="Version conflict"):
            await update_post(post_id, user_id, title="Updated", expected_version=1)


class TestDeletePost:
    @patch("app.repositories.post_repo.get_pool")
    async def test_delete_post_admin(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.post import soft_delete_post

        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        owner_id = uuid.uuid4()

        mock_conn.fetchrow.return_value = {"user_id": owner_id}
        mock_conn.execute.return_value = "UPDATE 1"
        mock_get_pool.return_value = mock_pool

        result = await soft_delete_post(post_id, user_id, is_admin=True)
        assert result is True

    @patch("app.repositories.post_repo.get_pool")
    async def test_delete_post_owner(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.post import soft_delete_post

        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        mock_conn.execute.return_value = "UPDATE 1"
        mock_get_pool.return_value = mock_pool

        result = await soft_delete_post(post_id, user_id, is_admin=False)
        assert result is True


class TestPinPost:
    @patch("app.repositories.post_repo.get_pool")
    async def test_pin_post_success(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.post import pin_post

        post_id = uuid.uuid4()
        mock_conn.execute.return_value = "UPDATE 1"
        mock_get_pool.return_value = mock_pool

        result = await pin_post(post_id, True)
        assert result is True

    @patch("app.repositories.post_repo.get_pool")
    async def test_pin_post_not_found(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.post import pin_post

        post_id = uuid.uuid4()
        mock_conn.execute.return_value = "UPDATE 0"
        mock_get_pool.return_value = mock_pool

        result = await pin_post(post_id, True)
        assert result is False


class TestTrendingPosts:
    @patch("app.repositories.post_repo.get_pool")
    async def test_get_trending(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.post import get_trending_posts

        mock_conn.fetch.return_value = [_make_post_row(), _make_post_row()]
        mock_get_pool.return_value = mock_pool

        result = await get_trending_posts(limit=5, days=7)
        assert len(result) == 2
        assert result[0]["title"] == "Test Post"


class TestGetPostWithView:
    @patch("app.repositories.post_repo.get_pool")
    async def test_get_post_increments_view(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.post import get_post_by_id

        post_id = uuid.uuid4()
        mock_conn.fetchrow.return_value = _make_post_row()
        mock_get_pool.return_value = mock_pool

        result = await get_post_by_id(post_id, increment_view=True)
        assert result is not None
        assert result["title"] == "Test Post"
        # increment_view_count should have been called (via execute on pool)
        assert mock_conn.execute.call_count >= 1


class TestSearchRepo:
    @patch("app.repositories.post_repo.get_pool")
    async def test_search_uses_websearch_to_tsquery(self, mock_get_pool, mock_pool, mock_conn):
        """search() should use websearch_to_tsquery, not to_tsquery."""
        from app.repositories.post_repo import search

        mock_conn.fetch.return_value = []
        mock_conn.fetchval.return_value = 0
        mock_get_pool.return_value = mock_pool

        await search(keyword="hello world")
        # Verify the SQL uses websearch_to_tsquery
        call_args = mock_conn.fetch.call_args
        sql = call_args[0][0]
        assert "websearch_to_tsquery" in sql
        assert "to_tsquery" not in sql.replace("websearch_to_tsquery", "")

    @patch("app.repositories.post_repo.get_pool")
    async def test_search_or_logic(self, mock_get_pool, mock_pool, mock_conn):
        """search() with logic=OR should join terms with OR."""
        from app.repositories.post_repo import search

        mock_conn.fetch.return_value = []
        mock_conn.fetchval.return_value = 0
        mock_get_pool.return_value = mock_pool

        await search(keyword="AI learning", logic="OR")
        call_args = mock_conn.fetch.call_args
        # The second positional arg is the keyword param
        keyword_param = call_args[0][1]
        assert "OR" in keyword_param

    @patch("app.repositories.post_repo.get_pool")
    async def test_search_or_logic_preserves_quoted_phrases(
        self, mock_get_pool, mock_pool, mock_conn
    ):
        """OR search with a quoted phrase must not split inside the quotes."""
        from app.repositories.post_repo import search

        mock_conn.fetch.return_value = []
        mock_conn.fetchval.return_value = 0
        mock_get_pool.return_value = mock_pool

        await search(keyword='"hello world" apple', logic="OR")
        call_args = mock_conn.fetch.call_args
        keyword_param = call_args[0][1]
        # Quoted phrase must remain intact and joined with OR
        assert '"hello world"' in keyword_param
        assert "OR" in keyword_param

    @patch("app.repositories.post_repo.get_pool")
    async def test_search_date_to_uses_exclusive_upper_bound(
        self, mock_get_pool, mock_pool, mock_conn
    ):
        """date_to filter should use < (date + 1 day) to include the entire end date.

        The +1 day is now computed in Python (timedelta) and passed as a plain
        parameter to avoid asyncpg type-inference issues with SQL INTERVAL
        arithmetic on parameterised timestamps.
        """
        from datetime import datetime

        from app.repositories.post_repo import search

        mock_conn.fetch.return_value = []
        mock_conn.fetchval.return_value = 0
        mock_get_pool.return_value = mock_pool

        await search(date_to=date(2023, 10, 1))
        call_args = mock_conn.fetch.call_args
        sql = call_args[0][0]
        assert "created_at <" in sql
        # Must NOT use <= with direct timestamptz cast
        assert "created_at <=" not in sql
        # The bound param should be 2023-10-02 (date_to + 1 day)
        params = call_args[0][1:]
        expected_end = datetime(2023, 10, 2)
        assert expected_end in params

    @patch("app.repositories.post_repo.get_pool")
    async def test_search_sort_oldest(self, mock_get_pool, mock_pool, mock_conn):
        """search() with sort=oldest should use ASC order."""
        from app.repositories.post_repo import search

        mock_conn.fetch.return_value = []
        mock_conn.fetchval.return_value = 0
        mock_get_pool.return_value = mock_pool

        await search(keyword="test", sort="oldest")
        call_args = mock_conn.fetch.call_args
        sql = call_args[0][0]
        assert "ASC" in sql

    @patch("app.repositories.post_repo.get_pool")
    async def test_search_sort_most_comments(self, mock_get_pool, mock_pool, mock_conn):
        """search() with sort=most_comments should order by comment_count."""
        from app.repositories.post_repo import search

        mock_conn.fetch.return_value = []
        mock_conn.fetchval.return_value = 0
        mock_get_pool.return_value = mock_pool

        await search(keyword="test", sort="most_comments")
        call_args = mock_conn.fetch.call_args
        sql = call_args[0][0]
        assert "comment_count" in sql


class TestFindHistory:
    @patch("app.repositories.post_repo.get_pool")
    async def test_find_history_default_limit(self, mock_get_pool, mock_pool, mock_conn):
        """find_history() should pass LIMIT $2 with default limit=50."""
        from app.repositories.post_repo import find_history

        mock_conn.fetch.return_value = []
        mock_get_pool.return_value = mock_pool

        post_id = uuid.uuid4()
        await find_history(post_id)

        call_args = mock_conn.fetch.call_args
        sql = call_args[0][0]
        assert "LIMIT $2" in sql
        # Default limit=50 should be the second positional arg
        assert call_args[0][2] == 50

    @patch("app.repositories.post_repo.get_pool")
    async def test_find_history_custom_limit(self, mock_get_pool, mock_pool, mock_conn):
        """find_history(limit=10) should pass limit=10."""
        from app.repositories.post_repo import find_history

        mock_conn.fetch.return_value = []
        mock_get_pool.return_value = mock_pool

        post_id = uuid.uuid4()
        await find_history(post_id, limit=10)

        call_args = mock_conn.fetch.call_args
        sql = call_args[0][0]
        assert "LIMIT $2" in sql
        assert call_args[0][2] == 10

    @patch("app.repositories.post_repo.get_pool")
    async def test_find_history_returns_dicts(self, mock_get_pool, mock_pool, mock_conn):
        """find_history() should return list of dicts from rows."""
        from app.repositories.post_repo import find_history

        fake_row = {
            "id": uuid.uuid4(),
            "post_id": uuid.uuid4(),
            "version": 1,
            "title": "V1",
            "content": "body",
        }
        mock_conn.fetch.return_value = [fake_row]
        mock_get_pool.return_value = mock_pool

        result = await find_history(uuid.uuid4())
        assert len(result) == 1
        assert result[0]["title"] == "V1"


# ---------------------------------------------------------------------------
# Cursor helpers
# ---------------------------------------------------------------------------


class TestCursorHelpers:
    def test_encode_decode_roundtrip_newest(self):
        from app.repositories.post_repo import _decode_cursor, _encode_cursor

        post_id = uuid.uuid4()
        now_iso = datetime.now(timezone.utc).isoformat()
        encoded = _encode_cursor(now_iso, post_id, "newest")
        sort, primary_val, decoded_id = _decode_cursor(encoded)
        assert sort == "newest"
        assert primary_val == now_iso
        assert decoded_id == post_id

    def test_encode_decode_roundtrip_popular(self):
        from app.repositories.post_repo import _decode_cursor, _encode_cursor

        post_id = uuid.uuid4()
        encoded = _encode_cursor("42", post_id, "popular")
        sort, primary_val, decoded_id = _decode_cursor(encoded)
        assert sort == "popular"
        assert primary_val == "42"
        assert decoded_id == post_id

    def test_decode_invalid_cursor_raises(self):
        from app.repositories.post_repo import _decode_cursor

        with pytest.raises(ValueError, match="Invalid cursor"):
            _decode_cursor("not-valid-base64!!!")

    def test_decode_cursor_wrong_format_raises(self):
        import base64

        from app.repositories.post_repo import _decode_cursor

        # Valid base64 but wrong segment count
        bad = base64.urlsafe_b64encode(b"onlytwoparts|x").decode()
        with pytest.raises(ValueError, match="Invalid cursor"):
            _decode_cursor(bad)


# ---------------------------------------------------------------------------
# find_many — cursor mode
# ---------------------------------------------------------------------------


class TestFindManyCursorMode:
    @patch("app.repositories.post_repo.get_pool")
    async def test_cursor_mode_returns_dict_keys(self, mock_get_pool, mock_pool, mock_conn):
        """find_many with cursor returns dict with expected keys."""
        from app.repositories.post_repo import _encode_cursor, find_many

        now = datetime.now(timezone.utc)
        post_id = uuid.uuid4()
        cursor = _encode_cursor(now.isoformat(), post_id, "newest")

        mock_conn.fetch.return_value = []
        mock_get_pool.return_value = mock_pool

        result = await find_many(cursor=cursor)
        assert "posts" in result
        assert "next_cursor" in result
        assert "has_more" in result
        assert result["total"] is None
        assert result["total_pages"] is None

    @patch("app.repositories.post_repo.get_pool")
    async def test_cursor_mode_has_more_false_when_fewer_than_page_size(
        self, mock_get_pool, mock_pool, mock_conn
    ):
        """has_more=False when returned rows <= page_size."""
        from app.repositories.post_repo import _encode_cursor, find_many

        now = datetime.now(timezone.utc)
        cursor = _encode_cursor(now.isoformat(), uuid.uuid4(), "newest")

        # Return exactly page_size rows (no extra)
        rows = [_make_post_row() for _ in range(5)]
        mock_conn.fetch.return_value = rows
        mock_get_pool.return_value = mock_pool

        result = await find_many(page_size=5, cursor=cursor)
        assert result["has_more"] is False
        assert result["next_cursor"] is None
        assert len(result["posts"]) == 5

    @patch("app.repositories.post_repo.get_pool")
    async def test_cursor_mode_has_more_true_when_extra_row(
        self, mock_get_pool, mock_pool, mock_conn
    ):
        """has_more=True and next_cursor set when page_size+1 rows returned."""
        from app.repositories.post_repo import _encode_cursor, find_many

        now = datetime.now(timezone.utc)
        cursor = _encode_cursor(now.isoformat(), uuid.uuid4(), "newest")

        # page_size=3, repo fetches 4 rows → has_more=True, posts truncated to 3
        rows = [_make_post_row() for _ in range(4)]
        mock_conn.fetch.return_value = rows
        mock_get_pool.return_value = mock_pool

        result = await find_many(page_size=3, cursor=cursor)
        assert result["has_more"] is True
        assert result["next_cursor"] is not None
        assert len(result["posts"]) == 3

    @patch("app.repositories.post_repo.get_pool")
    async def test_cursor_mode_oldest_uses_gt_comparison(self, mock_get_pool, mock_pool, mock_conn):
        """sort=oldest cursor mode should use > (ASC) comparison in WHERE clause."""
        from app.repositories.post_repo import _encode_cursor, find_many

        now = datetime.now(timezone.utc)
        cursor = _encode_cursor(now.isoformat(), uuid.uuid4(), "oldest")

        mock_conn.fetch.return_value = []
        mock_get_pool.return_value = mock_pool

        await find_many(sort="oldest", cursor=cursor)
        sql = mock_conn.fetch.call_args[0][0]
        assert ">" in sql
        assert "<" not in sql.split("WHERE")[1].split("ORDER")[0]

    @patch("app.repositories.post_repo.get_pool")
    async def test_cursor_mode_newest_uses_lt_comparison(self, mock_get_pool, mock_pool, mock_conn):
        """sort=newest cursor mode should use < (DESC) comparison in WHERE clause."""
        from app.repositories.post_repo import _encode_cursor, find_many

        now = datetime.now(timezone.utc)
        cursor = _encode_cursor(now.isoformat(), uuid.uuid4(), "newest")

        mock_conn.fetch.return_value = []
        mock_get_pool.return_value = mock_pool

        await find_many(sort="newest", cursor=cursor)
        sql = mock_conn.fetch.call_args[0][0]
        # WHERE clause should contain < but not > for keyset condition
        where_part = sql.split("WHERE")[1].split("ORDER")[0]
        assert "<" in where_part

    @patch("app.repositories.post_repo.get_pool")
    async def test_cursor_mode_popular_uses_like_count(self, mock_get_pool, mock_pool, mock_conn):
        """sort=popular cursor should reference like_count in WHERE clause."""
        from app.repositories.post_repo import _encode_cursor, find_many

        cursor = _encode_cursor("15", uuid.uuid4(), "popular")

        mock_conn.fetch.return_value = []
        mock_get_pool.return_value = mock_pool

        await find_many(sort="popular", cursor=cursor)
        sql = mock_conn.fetch.call_args[0][0]
        assert "like_count" in sql

    @patch("app.repositories.post_repo.get_pool")
    async def test_cursor_mode_popular_next_cursor_encodes_like_count(
        self, mock_get_pool, mock_pool, mock_conn
    ):
        """popular sort: next_cursor primary_val must be like_count, not created_at."""
        from app.repositories.post_repo import _decode_cursor, _encode_cursor, find_many

        cursor = _encode_cursor("10", uuid.uuid4(), "popular")

        # Return page_size+1 rows so has_more=True; page_size=2, so 3 rows fetched.
        # After trimming to page_size=2, last = rows[1], so inject like_count there.
        rows = [_make_post_row() for _ in range(3)]
        rows[1]["like_count"] = 7  # rows[1] is the last row kept after trim to page_size=2
        mock_conn.fetch.return_value = rows
        mock_get_pool.return_value = mock_pool

        result = await find_many(page_size=2, sort="popular", cursor=cursor)
        assert result["has_more"] is True
        assert result["next_cursor"] is not None
        _sort, primary_val, _id = _decode_cursor(result["next_cursor"])
        assert _sort == "popular"
        # primary_val should be the like_count of the last kept row (7)
        assert primary_val == "7"

    @patch("app.repositories.post_repo.get_pool")
    async def test_cursor_sort_overrides_query_sort(self, mock_get_pool, mock_pool, mock_conn):
        """When cursor encodes 'newest' but query says sort='oldest', the cursor's
        embedded sort must govern both ORDER BY direction and WHERE comparison."""
        from app.repositories.post_repo import _encode_cursor, find_many

        now = datetime.now(timezone.utc)
        # Cursor was created for 'newest' (DESC) pagination
        cursor = _encode_cursor(now.isoformat(), uuid.uuid4(), "newest")

        mock_conn.fetch.return_value = []
        mock_get_pool.return_value = mock_pool

        # Caller passes sort="oldest" — cursor sort should win
        await find_many(sort="oldest", cursor=cursor)
        sql = mock_conn.fetch.call_args[0][0]

        # ORDER BY must use DESC (newest) not ASC (oldest)
        assert "DESC" in sql
        # WHERE clause must use < (DESC comparison), not >
        where_part = sql.split("WHERE")[1].split("ORDER")[0]
        assert "<" in where_part
        assert ">" not in where_part

    @patch("app.repositories.post_repo.get_pool")
    async def test_cursor_mode_null_like_count_encodes_zero(
        self, mock_get_pool, mock_pool, mock_conn
    ):
        """NULL like_count in DB row must be encoded as '0', not 'None'."""
        from app.repositories.post_repo import _decode_cursor, _encode_cursor, find_many

        cursor = _encode_cursor("5", uuid.uuid4(), "popular")

        rows = [_make_post_row() for _ in range(2)]
        rows[0]["like_count"] = None  # explicitly NULL
        mock_conn.fetch.return_value = rows
        mock_get_pool.return_value = mock_pool

        result = await find_many(page_size=1, sort="popular", cursor=cursor)
        assert result["has_more"] is True
        assert result["next_cursor"] is not None
        _sort, primary_val, _id = _decode_cursor(result["next_cursor"])
        # Must be a valid integer string, not "None"
        assert primary_val.lstrip("-").isdigit()
        assert primary_val == "0"


# ---------------------------------------------------------------------------
# find_many — OFFSET mode backward compat
# ---------------------------------------------------------------------------


class TestFindManyOffsetMode:
    @patch("app.repositories.post_repo.get_pool")
    async def test_offset_mode_returns_dict_with_total(self, mock_get_pool, mock_pool, mock_conn):
        """find_many without cursor returns dict with total and total_pages."""
        from app.repositories.post_repo import find_many

        row = _make_post_row()
        row["_total"] = 1
        mock_conn.fetch.return_value = [row]
        mock_get_pool.return_value = mock_pool

        result = await find_many(page=1, page_size=20)
        assert result["total"] == 1
        assert result["total_pages"] == 1
        # OFFSET page is the last page (1 of 1), so no cursor / has_more
        assert result["next_cursor"] is None
        assert result["has_more"] is False
        assert len(result["posts"]) == 1

    @patch("app.repositories.post_repo.get_pool")
    async def test_offset_mode_empty_page_returns_count(self, mock_get_pool, mock_pool, mock_conn):
        """find_many OFFSET with no rows falls back to COUNT query."""
        from app.repositories.post_repo import find_many

        mock_conn.fetch.return_value = []
        mock_conn.fetchval.return_value = 42
        mock_get_pool.return_value = mock_pool

        result = await find_many(page=99, page_size=20)
        assert result["total"] == 42
        assert result["posts"] == []


# ---------------------------------------------------------------------------
# list_posts service
# ---------------------------------------------------------------------------


class TestListPostsService:
    @patch("app.repositories.post_repo.get_pool")
    async def test_list_posts_offset_mode(self, mock_get_pool, mock_pool, mock_conn):
        """list_posts without cursor returns dict with total/total_pages."""
        from app.services.post import list_posts

        row = _make_post_row()
        row["_total"] = 3
        mock_conn.fetch.return_value = [row]
        mock_get_pool.return_value = mock_pool

        result = await list_posts(page=1, page_size=20)
        assert result["total"] == 3
        assert result["total_pages"] == 1
        assert len(result["posts"]) == 1

    @patch("app.repositories.post_repo.get_pool")
    async def test_list_posts_cursor_mode(self, mock_get_pool, mock_pool, mock_conn):
        """list_posts with cursor returns dict with has_more/next_cursor."""
        from app.repositories.post_repo import _encode_cursor
        from app.services.post import list_posts

        now = datetime.now(timezone.utc)
        cursor = _encode_cursor(now.isoformat(), uuid.uuid4(), "newest")

        mock_conn.fetch.return_value = []
        mock_get_pool.return_value = mock_pool

        result = await list_posts(cursor=cursor)
        assert "has_more" in result
        assert result["has_more"] is False
        assert result["total"] is None

    @patch("app.repositories.post_repo.get_pool")
    async def test_list_posts_invalid_cursor_raises(self, mock_get_pool, mock_pool, mock_conn):
        """list_posts propagates ValueError from bad cursor."""
        from app.services.post import list_posts

        mock_get_pool.return_value = mock_pool
        with pytest.raises(ValueError, match="Invalid cursor"):
            await list_posts(cursor="!!bad!!")


# ---------------------------------------------------------------------------
# GET /posts endpoint — cursor and OFFSET modes
# ---------------------------------------------------------------------------


class TestGetPostsEndpoint:
    @patch("app.api.v1.endpoints.posts.list_posts")
    @patch("app.api.v1.endpoints.posts.get_current_user")
    async def test_get_posts_offset_returns_total(self, mock_auth, mock_list, client):
        """GET /posts without cursor returns total/total_pages (backward compat)."""
        from app.core.deps import get_current_user

        mock_auth.return_value = {"sub": str(uuid.uuid4()), "role": "MEMBER"}
        mock_list.return_value = {
            "posts": [],
            "total": 10,
            "total_pages": 1,
            "next_cursor": None,
            "has_more": None,
        }

        from app.main import app

        app.dependency_overrides[get_current_user] = lambda: {
            "sub": str(uuid.uuid4()),
            "role": "MEMBER",
        }
        response = await client.get("/api/v1/posts")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 10
        assert data["total_pages"] == 1
        assert "has_more" in data

    @patch("app.api.v1.endpoints.posts.list_posts")
    async def test_get_posts_cursor_returns_next_cursor(self, mock_list, client):
        """GET /posts?cursor=... returns next_cursor and has_more."""
        from app.core.deps import get_current_user
        from app.repositories.post_repo import _encode_cursor

        now = datetime.now(timezone.utc)
        fake_cursor = _encode_cursor(now.isoformat(), uuid.uuid4(), "newest")

        mock_list.return_value = {
            "posts": [],
            "total": None,
            "total_pages": None,
            "next_cursor": fake_cursor,
            "has_more": True,
        }

        from app.main import app

        app.dependency_overrides[get_current_user] = lambda: {
            "sub": str(uuid.uuid4()),
            "role": "MEMBER",
        }
        response = await client.get(f"/api/v1/posts?cursor={fake_cursor}")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["next_cursor"] == fake_cursor
        assert data["has_more"] is True

    @patch("app.api.v1.endpoints.posts.list_posts")
    async def test_get_posts_invalid_cursor_returns_400(self, mock_list, client):
        """GET /posts?cursor=invalid returns 400."""
        from app.core.deps import get_current_user

        mock_list.side_effect = ValueError("Invalid cursor: bad format")

        from app.main import app

        app.dependency_overrides[get_current_user] = lambda: {
            "sub": str(uuid.uuid4()),
            "role": "MEMBER",
        }
        response = await client.get("/api/v1/posts?cursor=!!bad!!")
        app.dependency_overrides.clear()

        assert response.status_code == 400
        assert "Invalid cursor" in response.json()["detail"]["message"]

    @patch("app.api.v1.endpoints.posts.list_posts")
    async def test_get_posts_cursor_has_more_false(self, mock_list, client):
        """GET /posts?cursor=... with no more pages returns has_more=False and next_cursor=None."""
        from app.core.deps import get_current_user
        from app.repositories.post_repo import _encode_cursor

        now = datetime.now(timezone.utc)
        fake_cursor = _encode_cursor(now.isoformat(), uuid.uuid4(), "oldest")

        mock_list.return_value = {
            "posts": [],
            "total": None,
            "total_pages": None,
            "next_cursor": None,
            "has_more": False,
        }

        from app.main import app

        app.dependency_overrides[get_current_user] = lambda: {
            "sub": str(uuid.uuid4()),
            "role": "MEMBER",
        }
        response = await client.get(f"/api/v1/posts?cursor={fake_cursor}&sort=oldest")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["has_more"] is False
        assert data["next_cursor"] is None

    @patch("app.api.v1.endpoints.posts.list_posts")
    async def test_get_posts_passes_sig_id_to_service(self, mock_list, client):
        """GET /posts?sig_id=... must forward sig_id to list_posts service."""
        from app.core.deps import get_current_user

        sig_id = str(uuid.uuid4())
        mock_list.return_value = {
            "posts": [],
            "total": 0,
            "total_pages": 1,
            "next_cursor": None,
            "has_more": None,
        }

        from app.main import app

        app.dependency_overrides[get_current_user] = lambda: {
            "sub": str(uuid.uuid4()),
            "role": "MEMBER",
        }
        response = await client.get(f"/api/v1/posts?sig_id={sig_id}")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        # Verify sig_id was forwarded to the service call
        call_kwargs = mock_list.call_args.kwargs
        assert call_kwargs.get("sig_id") == sig_id
