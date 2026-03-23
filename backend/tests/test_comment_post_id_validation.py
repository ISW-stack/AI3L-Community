"""Tests for Bug #2: comment edit endpoint must verify post_id ownership."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

_EP = "app.api.v1.endpoints.comments"


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


def _make_comment(post_id=None, user_id=None, comment_id=None):
    now = datetime.now(timezone.utc).isoformat()
    uid = user_id or str(uuid.uuid4())
    return {
        "id": str(comment_id or uuid.uuid4()),
        "post_id": str(post_id or uuid.uuid4()),
        "content": "Test comment",
        "author": {
            "id": uid,
            "username": "testuser",
            "display_name": "Test User",
            "avatar_url": None,
        },
        "parent_id": None,
        "mentions": None,
        "reaction_counts": None,
        "user_reactions": None,
        "_raw_reactions": None,
        "created_at": now,
        "updated_at": now,
    }


class TestEditCommentPostIdValidation:
    """Verify that editing a comment with wrong post_id returns 404."""

    @pytest.mark.anyio
    async def test_edit_comment_wrong_post_id_returns_404(self, client):
        """PUT /posts/{wrong_pid}/comments/{cid} → 404 when comment belongs to different post."""
        wrong_post_id = uuid.uuid4()
        comment_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP}.sanitize_html", return_value="Updated content"),
                patch(
                    f"{_EP}.update_comment", new_callable=AsyncMock, return_value=None
                ) as mock_update,
            ):
                resp = await client.put(
                    f"/api/v1/posts/{wrong_post_id}/comments/{comment_id}",
                    json={"content": "Updated content"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
                data = resp.json()
                assert data["detail"]["code"] == "SYS_404"
                # Verify post_id was passed through to update_comment
                mock_update.assert_called_once_with(
                    comment_id=comment_id,
                    user_id=user_id,
                    content="Updated content",
                    post_id=wrong_post_id,
                )
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_edit_comment_correct_post_id_succeeds(self, client):
        """PUT /posts/{correct_pid}/comments/{cid} → 200 when post_id matches."""
        post_id = uuid.uuid4()
        comment_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        comment = _make_comment(post_id=post_id, user_id=user_id, comment_id=comment_id)
        comment["content"] = "Updated content"

        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP}.sanitize_html", return_value="Updated content"),
                patch(
                    f"{_EP}.update_comment", new_callable=AsyncMock, return_value=comment
                ) as mock_update,
            ):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}/comments/{comment_id}",
                    json={"content": "Updated content"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["content"] == "Updated content"
                # Verify post_id was passed through
                mock_update.assert_called_once_with(
                    comment_id=comment_id,
                    user_id=user_id,
                    content="Updated content",
                    post_id=post_id,
                )
        finally:
            _clear_overrides()


class TestCommentRepoUpdatePostIdFilter:
    """Verify comment_repo.update filters by post_id when provided."""

    @pytest.mark.anyio
    async def test_repo_update_with_post_id(self, mock_pool, mock_conn):
        """comment_repo.update includes post_id in WHERE clause when provided."""
        comment_id = uuid.uuid4()
        user_id = uuid.uuid4()
        post_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        mock_row = {
            "id": comment_id,
            "post_id": post_id,
            "user_id": user_id,
            "parent_id": None,
            "content": "updated",
            "mentions": None,
            "reactions": {},
            "created_at": now,
            "updated_at": now,
            "author_id": user_id,
            "author_username": "testuser",
            "author_display_name": "Test User",
            "author_avatar_url": None,
        }
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        with patch("app.repositories.comment_repo.get_pool", return_value=mock_pool):
            from app.repositories.comment_repo import update

            result = await update(comment_id, user_id, "updated", post_id)

        assert result is not None
        assert result["id"] == comment_id
        # Verify the SQL query included post_id ($4)
        call_args = mock_conn.fetchrow.call_args
        sql = call_args[0][0]
        assert "post_id = $4" in sql
        # Verify all 4 params were passed
        assert call_args[0][1] == "updated"  # content
        assert call_args[0][2] == comment_id
        assert call_args[0][3] == user_id
        assert call_args[0][4] == post_id

    @pytest.mark.anyio
    async def test_repo_update_without_post_id(self, mock_pool, mock_conn):
        """comment_repo.update omits post_id filter when not provided."""
        comment_id = uuid.uuid4()
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        mock_row = {
            "id": comment_id,
            "post_id": uuid.uuid4(),
            "user_id": user_id,
            "parent_id": None,
            "content": "updated",
            "mentions": None,
            "reactions": {},
            "created_at": now,
            "updated_at": now,
            "author_id": user_id,
            "author_username": "testuser",
            "author_display_name": "Test User",
            "author_avatar_url": None,
        }
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        with patch("app.repositories.comment_repo.get_pool", return_value=mock_pool):
            from app.repositories.comment_repo import update

            result = await update(comment_id, user_id, "updated")

        assert result is not None
        call_args = mock_conn.fetchrow.call_args
        sql = call_args[0][0]
        assert "post_id = $4" not in sql
        # Only 3 params: content, comment_id, user_id
        assert len(call_args[0]) == 4  # sql + 3 params

    @pytest.mark.anyio
    async def test_repo_update_wrong_post_id_returns_none(self, mock_pool, mock_conn):
        """comment_repo.update returns None when post_id doesn't match."""
        comment_id = uuid.uuid4()
        user_id = uuid.uuid4()
        wrong_post_id = uuid.uuid4()

        mock_conn.fetchrow = AsyncMock(return_value=None)

        with patch("app.repositories.comment_repo.get_pool", return_value=mock_pool):
            from app.repositories.comment_repo import update

            result = await update(comment_id, user_id, "updated", wrong_post_id)

        assert result is None


class TestServiceUpdateCommentPassesPostId:
    """Verify service layer passes post_id to repo."""

    @pytest.mark.anyio
    async def test_service_passes_post_id_to_repo(self):
        """update_comment passes post_id to comment_repo.update."""
        comment_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        post_id = uuid.uuid4()

        with patch(
            "app.services.comment.comment_repo.update",
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_repo_update:
            from app.services.comment import update_comment

            result = await update_comment(comment_id, user_id, "content", post_id)

        assert result is None
        mock_repo_update.assert_called_once_with(comment_id, uuid.UUID(user_id), "content", post_id)

    @pytest.mark.anyio
    async def test_service_without_post_id(self):
        """update_comment defaults post_id to None when not provided."""
        comment_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        with patch(
            "app.services.comment.comment_repo.update",
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_repo_update:
            from app.services.comment import update_comment

            result = await update_comment(comment_id, user_id, "content")

        assert result is None
        mock_repo_update.assert_called_once_with(comment_id, uuid.UUID(user_id), "content", None)
