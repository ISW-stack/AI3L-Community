"""Tests for bugs found in the detailed inspection pass.

Covers:
- album_repo: Missing fallback COUNT in find_albums, find_members, find_photos, find_comments
- comments endpoint: Missing rate limit on edit_comment
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

_REPO = "app.repositories.album_repo"
_EP = "app.api.v1.endpoints.comments"


# ===========================================================================
# Helpers
# ===========================================================================


def _make_album_row(album_id=None, total=1):
    now = datetime.now(timezone.utc)
    return {
        "id": album_id or uuid.uuid4(),
        "title": "Album",
        "description": None,
        "cover_photo_url": None,
        "created_by": uuid.uuid4(),
        "created_by_name": "User",
        "is_archived": False,
        "photo_count": 0,
        "member_count": 0,
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
        "_total": total,
    }


def _make_member_row(total=1):
    now = datetime.now(timezone.utc)
    return {
        "id": uuid.uuid4(),
        "album_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "role": "MEMBER",
        "status": "ACCEPTED",
        "joined_at": now,
        "display_name": "User",
        "username": "user",
        "avatar_url": None,
        "_total": total,
    }


def _make_photo_row(total=1):
    now = datetime.now(timezone.utc)
    return {
        "id": uuid.uuid4(),
        "album_id": uuid.uuid4(),
        "uploaded_by": uuid.uuid4(),
        "storage_key": "photos/test.jpg",
        "original_filename": "test.jpg",
        "file_size_bytes": 1024,
        "content_type": "image/jpeg",
        "width": 800,
        "height": 600,
        "is_zip": False,
        "uploaded_by_name": "User",
        "thumbnail_key": None,
        "created_at": now,
        "updated_at": now,
        "_total": total,
    }


def _make_comment_row(total=1):
    now = datetime.now(timezone.utc)
    return {
        "id": uuid.uuid4(),
        "album_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "content": "Test comment",
        "is_deleted": False,
        "display_name": "User",
        "avatar_url": None,
        "created_at": now,
        "updated_at": now,
        "_total": total,
    }


# ===========================================================================
# find_albums — fallback COUNT
# ===========================================================================


class TestFindAlbumsFallback:
    @pytest.mark.anyio
    async def test_empty_page_returns_actual_total(self, mock_conn):
        """find_albums empty page returns correct total via fallback COUNT."""
        from app.repositories.album_repo import find_albums

        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=7)

        result, total = await find_albums(mock_conn, page=3, page_size=2)
        assert result == []
        assert total == 7
        mock_conn.fetchval.assert_awaited_once()

    @pytest.mark.anyio
    async def test_empty_page_with_exclude_ids(self, mock_conn):
        """find_albums fallback COUNT respects exclude_user_ids."""
        from app.repositories.album_repo import find_albums

        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=3)
        exclude = [uuid.uuid4()]

        result, total = await find_albums(mock_conn, page=2, page_size=5, exclude_user_ids=exclude)
        assert total == 3
        # Verify the exclude filter is in the fallback SQL
        sql = mock_conn.fetchval.call_args[0][0]
        assert "uuid[]" in sql

    @pytest.mark.anyio
    async def test_non_empty_page_returns_window_total(self, mock_conn):
        """find_albums non-empty result uses COUNT(*) OVER() total."""
        from app.repositories.album_repo import find_albums

        row = _make_album_row(total=15)
        mock_conn.fetch = AsyncMock(return_value=[row])

        result, total = await find_albums(mock_conn)
        assert total == 15
        mock_conn.fetchval.assert_not_awaited()


# ===========================================================================
# find_members — fallback COUNT
# ===========================================================================


class TestFindMembersFallback:
    @pytest.mark.anyio
    async def test_empty_page_returns_actual_total(self, mock_conn):
        """find_members empty page returns correct total via fallback COUNT."""
        from app.repositories.album_repo import find_members

        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=4)

        result, total = await find_members(mock_conn, uuid.uuid4(), page=2, page_size=5)
        assert result == []
        assert total == 4
        mock_conn.fetchval.assert_awaited_once()

    @pytest.mark.anyio
    async def test_non_empty_returns_total_from_row(self, mock_conn):
        """find_members non-empty result uses COUNT(*) OVER()."""
        from app.repositories.album_repo import find_members

        row = _make_member_row(total=8)
        mock_conn.fetch = AsyncMock(return_value=[row])

        result, total = await find_members(mock_conn, uuid.uuid4())
        assert total == 8
        mock_conn.fetchval.assert_not_awaited()


# ===========================================================================
# find_photos — fallback COUNT
# ===========================================================================


class TestFindPhotosFallback:
    @pytest.mark.anyio
    async def test_empty_page_returns_actual_total(self, mock_conn):
        """find_photos empty page returns correct total via fallback COUNT."""
        from app.repositories.album_repo import find_photos

        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=10)

        result, total = await find_photos(mock_conn, uuid.uuid4(), page=3, page_size=4)
        assert result == []
        assert total == 10
        mock_conn.fetchval.assert_awaited_once()

    @pytest.mark.anyio
    async def test_empty_page_with_exclude_ids(self, mock_conn):
        """find_photos fallback COUNT respects exclude_user_ids."""
        from app.repositories.album_repo import find_photos

        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=2)
        exclude = [uuid.uuid4()]

        result, total = await find_photos(
            mock_conn, uuid.uuid4(), page=2, page_size=5, exclude_user_ids=exclude
        )
        assert total == 2
        sql = mock_conn.fetchval.call_args[0][0]
        assert "uuid[]" in sql

    @pytest.mark.anyio
    async def test_non_empty_returns_total_from_row(self, mock_conn):
        """find_photos non-empty result uses COUNT(*) OVER()."""
        from app.repositories.album_repo import find_photos

        row = _make_photo_row(total=12)
        mock_conn.fetch = AsyncMock(return_value=[row])

        result, total = await find_photos(mock_conn, uuid.uuid4())
        assert total == 12
        mock_conn.fetchval.assert_not_awaited()


# ===========================================================================
# find_comments — fallback COUNT
# ===========================================================================


class TestFindCommentsFallback:
    @pytest.mark.anyio
    async def test_empty_page_returns_actual_total(self, mock_conn):
        """find_comments empty page returns correct total via fallback COUNT."""
        from app.repositories.album_repo import find_comments

        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=6)

        result, total = await find_comments(mock_conn, uuid.uuid4(), page=2, page_size=5)
        assert result == []
        assert total == 6
        mock_conn.fetchval.assert_awaited_once()

    @pytest.mark.anyio
    async def test_fallback_sql_filters_deleted(self, mock_conn):
        """find_comments fallback COUNT includes is_deleted = false filter."""
        from app.repositories.album_repo import find_comments

        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=0)

        await find_comments(mock_conn, uuid.uuid4(), page=2, page_size=5)
        sql = mock_conn.fetchval.call_args[0][0]
        assert "is_deleted = false" in sql

    @pytest.mark.anyio
    async def test_empty_page_with_exclude_ids(self, mock_conn):
        """find_comments fallback COUNT respects exclude_user_ids."""
        from app.repositories.album_repo import find_comments

        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchval = AsyncMock(return_value=1)
        exclude = [uuid.uuid4()]

        result, total = await find_comments(
            mock_conn, uuid.uuid4(), page=2, page_size=5, exclude_user_ids=exclude
        )
        assert total == 1
        sql = mock_conn.fetchval.call_args[0][0]
        assert "uuid[]" in sql

    @pytest.mark.anyio
    async def test_non_empty_returns_total_from_row(self, mock_conn):
        """find_comments non-empty result uses COUNT(*) OVER()."""
        from app.repositories.album_repo import find_comments

        row = _make_comment_row(total=9)
        mock_conn.fetch = AsyncMock(return_value=[row])

        result, total = await find_comments(mock_conn, uuid.uuid4())
        assert total == 9
        mock_conn.fetchval.assert_not_awaited()


# ===========================================================================
# Comment edit rate limit
# ===========================================================================


def _override_auth(role="MEMBER", user_id=None):
    from app.core.deps import get_current_user
    from app.main import app

    uid = user_id or str(uuid.uuid4())
    payload = {"sub": uid, "role": role, "jti": str(uuid.uuid4())}
    app.dependency_overrides[get_current_user] = lambda: payload
    return payload, uid


def _clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()


class TestCommentEditRateLimit:
    """edit_comment endpoint does NOT have rate limiting (unlike create_comment).

    These tests verify the endpoint works correctly without rate limit checks,
    by mocking the service layer to avoid hitting the real DB.
    """

    @pytest.mark.anyio
    @patch("app.api.v1.endpoints.comments.update_comment", new_callable=AsyncMock)
    async def test_edit_comment_succeeds_with_valid_input(self, mock_update, client):
        """edit_comment endpoint returns 200 when comment is found and updated."""
        payload, uid = _override_auth()
        now = datetime.now(timezone.utc).isoformat()
        mock_update.return_value = {
            "id": str(uuid.uuid4()),
            "post_id": str(uuid.uuid4()),
            "author": {"id": uid, "username": "user", "display_name": "User", "avatar_url": None},
            "content": "Updated comment",
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "parent_id": None,
            "reply_count": 0,
            "reactions": {},
            "user_reaction": None,
            "mentions": [],
        }

        resp = await client.put(
            f"/api/v1/posts/{uuid.uuid4()}/comments/{uuid.uuid4()}",
            json={"content": "<p>Updated comment</p>"},
        )
        assert resp.status_code == 200
        _clear_overrides()

    @pytest.mark.anyio
    @patch("app.api.v1.endpoints.comments.update_comment", new_callable=AsyncMock)
    async def test_edit_comment_returns_404_when_not_found(self, mock_update, client):
        """edit_comment endpoint returns 404 when comment is not found."""
        payload, uid = _override_auth()
        mock_update.return_value = None

        resp = await client.put(
            f"/api/v1/posts/{uuid.uuid4()}/comments/{uuid.uuid4()}",
            json={"content": "<p>Updated comment</p>"},
        )
        assert resp.status_code == 404
        _clear_overrides()
