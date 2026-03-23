"""Tests for comments endpoints — get, create, delete, toggle reaction."""

import uuid
from datetime import datetime, timezone
from unittest.mock import ANY, AsyncMock, MagicMock, patch

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


class TestCommentNotificationUsesPostId:
    """Verify comment.created event emits post_id (not comment_id) as entity_id."""

    @pytest.mark.anyio
    async def test_mention_notification_uses_post_id(self):
        """Mention targets should contain post_id, not comment_id."""

        post_id = uuid.uuid4()
        comment_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        mentioned_user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        mock_row = {
            "id": comment_id,
            "post_id": post_id,
            "user_id": uuid.UUID(user_id),
            "parent_id": None,
            "content": "Hello @bob",
            "mentions": ["bob"],
            "reactions": {},
            "created_at": now,
            "updated_at": now,
            "author_id": uuid.UUID(user_id),
            "author_username": "alice",
            "author_display_name": "Alice",
            "author_avatar_url": None,
        }

        mock_post = {"id": post_id, "allow_comments": True, "comment_count": 0}

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(side_effect=[mock_post, mock_row])
        conn.execute = AsyncMock()
        conn.fetch = AsyncMock(
            return_value=[{"id": uuid.UUID(mentioned_user_id), "username": "bob"}]
        )

        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        conn.transaction = MagicMock(return_value=tx)

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool_obj = MagicMock()
        mock_pool_obj.acquire.return_value = cm

        emit_calls = []

        async def mock_emit(event, **kwargs):
            emit_calls.append((event, kwargs))

        mock_redis = AsyncMock()
        mock_redis.smembers = AsyncMock(return_value=set())

        with (
            patch("app.services.comment.get_pool", return_value=mock_pool_obj),
            patch("app.services.comment.emit", side_effect=mock_emit),
            patch("app.converters.shared.resolve_avatar_url", return_value=None),
            patch(
                "app.repositories.post_repo.find_owner_id",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("app.services.comment.get_redis", return_value=mock_redis),
        ):
            from app.services.comment import create_comment

            await create_comment(
                post_id=post_id,
                user_id=user_id,
                content="Hello @bob",
                mentions=["bob"],
            )

        assert len(emit_calls) == 1
        event, kwargs = emit_calls[0]
        assert event == "comment.created"
        # mention_targets should contain post_id, NOT comment_id
        assert len(kwargs["mention_targets"]) == 1
        target_uid, entity_id = kwargs["mention_targets"][0]
        assert target_uid == mentioned_user_id
        assert entity_id == str(post_id)
        assert entity_id != str(comment_id)

    @pytest.mark.anyio
    async def test_reply_notification_uses_post_id(self):
        """Reply target should contain post_id, not comment_id."""

        post_id = uuid.uuid4()
        comment_id = uuid.uuid4()
        parent_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        parent_user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        mock_row = {
            "id": comment_id,
            "post_id": post_id,
            "user_id": uuid.UUID(user_id),
            "parent_id": parent_id,
            "content": "Reply here",
            "mentions": None,
            "reactions": {},
            "created_at": now,
            "updated_at": now,
            "author_id": uuid.UUID(user_id),
            "author_username": "alice",
            "author_display_name": "Alice",
            "author_avatar_url": None,
        }

        mock_post = {"id": post_id, "allow_comments": True, "comment_count": 0}
        mock_parent = {"id": parent_id}

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(side_effect=[mock_post, mock_parent, mock_row])
        conn.execute = AsyncMock()

        # find_parent_user_id
        parent_user_row = AsyncMock()
        parent_user_row.fetchrow = AsyncMock(return_value={"user_id": uuid.UUID(parent_user_id)})

        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        conn.transaction = MagicMock(return_value=tx)

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=False)

        mock_pool_obj = MagicMock()
        mock_pool_obj.acquire.return_value = cm

        emit_calls = []

        async def mock_emit(event, **kwargs):
            emit_calls.append((event, kwargs))

        mock_redis = AsyncMock()
        mock_redis.smembers = AsyncMock(return_value=set())

        with (
            patch("app.services.comment.get_pool", return_value=mock_pool_obj),
            patch("app.services.comment.emit", side_effect=mock_emit),
            patch("app.converters.shared.resolve_avatar_url", return_value=None),
            patch(
                "app.repositories.comment_repo.find_parent_user_id",
                new_callable=AsyncMock,
                return_value=parent_user_id,
            ),
            patch(
                "app.repositories.post_repo.find_owner_id",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("app.services.comment.get_redis", return_value=mock_redis),
        ):
            from app.services.comment import create_comment

            await create_comment(
                post_id=post_id,
                user_id=user_id,
                content="Reply here",
                parent_id=str(parent_id),
            )

        assert len(emit_calls) == 1
        event, kwargs = emit_calls[0]
        assert event == "comment.created"
        # reply_target should contain post_id, NOT comment_id
        reply_uid, entity_id = kwargs["reply_target"]
        assert reply_uid == parent_user_id
        assert entity_id == str(post_id)
        assert entity_id != str(comment_id)


class TestGetComments:
    @pytest.mark.anyio
    async def test_get_comments(self, client):
        """GET /posts/{pid}/comments → 200 with comment list."""
        post_id = uuid.uuid4()
        comment = _make_comment(post_id=post_id)

        try:
            _override_auth("MEMBER")
            with (
                patch(
                    f"{_EP}.get_post_by_id", new_callable=AsyncMock, return_value={"id": post_id}
                ),
                patch(f"{_EP}.list_comments", new_callable=AsyncMock, return_value=([comment], 1)),
            ):
                resp = await client.get(
                    f"/api/v1/posts/{post_id}/comments",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
                assert len(data["comments"]) == 1
        finally:
            _clear_overrides()


class TestGetCommentsPagination:
    @pytest.mark.anyio
    async def test_get_comments_with_page_params(self, client):
        """GET /posts/{pid}/comments accepts page/page_size (not offset/limit)."""
        post_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with (
                patch(
                    f"{_EP}.get_post_by_id", new_callable=AsyncMock, return_value={"id": post_id}
                ),
                patch(
                    f"{_EP}.list_comments", new_callable=AsyncMock, return_value=([], 0)
                ) as mock_list,
            ):
                resp = await client.get(
                    f"/api/v1/posts/{post_id}/comments?page=2&page_size=10",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                mock_list.assert_called_once_with(post_id, page=2, page_size=10, viewer_id=ANY)
        finally:
            _clear_overrides()


class TestCreateComment:
    @pytest.mark.anyio
    async def test_create_comment(self, client):
        """POST /posts/{pid}/comments → 201."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        comment = _make_comment(post_id=post_id, user_id=user_id)

        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.create_comment", new_callable=AsyncMock, return_value=comment),
            ):
                resp = await client.post(
                    f"/api/v1/posts/{post_id}/comments",
                    json={"content": "Test comment"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 201
                assert resp.json()["content"] == "Test comment"
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_create_comment_empty_after_sanitize(self, client):
        """POST /posts/{pid}/comments → 400 when sanitized content is empty (script-only)."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.sanitize_html", return_value=""),
            ):
                resp = await client.post(
                    f"/api/v1/posts/{post_id}/comments",
                    json={"content": "<script>alert(1)</script>"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 400
                assert "empty" in resp.json()["detail"]["message"].lower()
        finally:
            _clear_overrides()


class TestEditComment:
    @pytest.mark.anyio
    async def test_edit_comment_empty_after_sanitize(self, client):
        """PUT /posts/{pid}/comments/{cid} → 400 when sanitized content is empty."""
        post_id = uuid.uuid4()
        comment_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.sanitize_html", return_value=""):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}/comments/{comment_id}",
                    json={"content": "<script>alert(1)</script>"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 400
                assert "empty" in resp.json()["detail"]["message"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_edit_comment_whitespace_after_sanitize(self, client):
        """PUT /posts/{pid}/comments/{cid} → 400 when sanitized content is whitespace."""
        post_id = uuid.uuid4()
        comment_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.sanitize_html", return_value="   "):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}/comments/{comment_id}",
                    json={"content": "   "},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 400
                assert "empty" in resp.json()["detail"]["message"].lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_edit_comment_valid_content(self, client):
        """PUT /posts/{pid}/comments/{cid} → 200 with valid sanitized content."""
        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        comment_id = uuid.uuid4()
        comment = _make_comment(post_id=post_id, user_id=user_id, comment_id=comment_id)
        comment["content"] = "Updated comment"

        try:
            _override_auth("MEMBER", user_id=user_id)
            with (
                patch(f"{_EP}.sanitize_html", return_value="Updated comment"),
                patch(f"{_EP}.update_comment", new_callable=AsyncMock, return_value=comment),
            ):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}/comments/{comment_id}",
                    json={"content": "Updated comment"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["content"] == "Updated comment"
        finally:
            _clear_overrides()


class TestDeleteComment:
    @pytest.mark.anyio
    async def test_delete_comment(self, client):
        """DELETE /posts/{pid}/comments/{cid} → 200."""
        post_id = uuid.uuid4()
        comment_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.soft_delete_comment", new_callable=AsyncMock, return_value=True):
                resp = await client.delete(
                    f"/api/v1/posts/{post_id}/comments/{comment_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
        finally:
            _clear_overrides()


class TestToggleReaction:
    @pytest.mark.anyio
    async def test_toggle_reaction(self, client):
        """POST /posts/{pid}/comments/{cid}/reactions → 200."""
        post_id = uuid.uuid4()
        comment_id = uuid.uuid4()
        comment = _make_comment(post_id=post_id, comment_id=comment_id)
        comment["reaction_counts"] = {"LIKE": 1}
        comment["user_reactions"] = None
        comment["_raw_reactions"] = {"LIKE": [str(uuid.uuid4())]}

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(f"{_EP}.add_reaction", new_callable=AsyncMock, return_value=comment),
            ):
                resp = await client.post(
                    f"/api/v1/posts/{post_id}/comments/{comment_id}/reactions",
                    json={"reaction": "LIKE"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert "LIKE" in resp.json()["reaction_counts"]
        finally:
            _clear_overrides()


class TestToggleReactionRateLimit:
    @pytest.mark.anyio
    async def test_toggle_reaction_rate_limited(self, client):
        """POST /posts/{pid}/comments/{cid}/reactions → 429 when rate limited."""
        post_id = uuid.uuid4()
        comment_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=False):
                resp = await client.post(
                    f"/api/v1/posts/{post_id}/comments/{comment_id}/reactions",
                    json={"reaction": "LIKE"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 429
        finally:
            _clear_overrides()


class TestEditCommentNotFound:
    @pytest.mark.anyio
    async def test_edit_comment_not_found_returns_404(self, client):
        """PUT /posts/{pid}/comments/{cid} → 404 with SYS_404 when comment not found."""
        post_id = uuid.uuid4()
        comment_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_EP}.sanitize_html", return_value="Updated content"),
                patch(f"{_EP}.update_comment", new_callable=AsyncMock, return_value=None),
            ):
                resp = await client.put(
                    f"/api/v1/posts/{post_id}/comments/{comment_id}",
                    json={"content": "Updated content"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
                data = resp.json()
                assert data["detail"]["code"] == "SYS_404"
                assert "not found or you are not the owner" in data["detail"]["message"].lower()
        finally:
            _clear_overrides()


class TestDeleteCommentNotFound:
    @pytest.mark.anyio
    async def test_delete_comment_not_found_returns_404(self, client):
        """DELETE /posts/{pid}/comments/{cid} → 404 with SYS_404 and consistent message."""
        post_id = uuid.uuid4()
        comment_id = uuid.uuid4()

        try:
            _override_auth("MEMBER")
            with patch(f"{_EP}.soft_delete_comment", new_callable=AsyncMock, return_value=False):
                resp = await client.delete(
                    f"/api/v1/posts/{post_id}/comments/{comment_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 404
                data = resp.json()
                assert data["detail"]["code"] == "SYS_404"
                assert "not found or you are not the owner" in data["detail"]["message"].lower()
        finally:
            _clear_overrides()


class TestSigMemberBatchNotification:
    """Verify _on_post_created_in_sig dispatches to Celery (no longer does in-process batching)."""

    @pytest.mark.anyio
    async def test_dispatches_celery_task(self):
        """_on_post_created_in_sig calls notify_sig_members_new_post.delay() with correct args."""
        from unittest.mock import MagicMock

        from app.event_handlers import _on_post_created_in_sig

        sig_id = str(uuid.uuid4())
        post_id = str(uuid.uuid4())
        author_id = str(uuid.uuid4())

        mock_task = MagicMock()
        with patch("app.tasks.event_retry.notify_sig_members_new_post", mock_task):
            await _on_post_created_in_sig(
                sig_id=sig_id,
                post_id=post_id,
                author_id=author_id,
                post_title="Test Post",
            )

        mock_task.delay.assert_called_once_with(sig_id, post_id, author_id, "Test Post")
