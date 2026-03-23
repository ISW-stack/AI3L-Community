"""Tests for cascade delete behaviour in user anonymization and SIG soft-delete,
plus the SIG posts viewer_id fix.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

_EP = "app.api.v1.endpoints.sigs"


# ── D1: anonymize_user cascade cleanup ──────────────────────────────


class TestAnonymizeUserCascade:
    """Verify that anonymize_user cleans up all related tables."""

    @patch("app.core.database.get_pool")
    @patch("app.repositories.user_repo.get_pool")
    async def test_anonymize_cleans_posts(self, mock_repo_pool, mock_db_pool, mock_pool, mock_conn):
        from app.services.user import anonymize_user

        mock_conn.execute.return_value = "UPDATE 1"
        mock_repo_pool.return_value = mock_pool
        mock_db_pool.return_value = mock_pool

        user_id = uuid.uuid4()
        await anonymize_user(user_id)

        # Verify posts soft-delete was called
        execute_calls = [str(c) for c in mock_conn.execute.call_args_list]
        post_calls = [c for c in execute_calls if "posts" in c and "is_deleted = true" in c]
        assert len(post_calls) >= 1, "Should soft-delete user's posts"

    @patch("app.core.database.get_pool")
    @patch("app.repositories.user_repo.get_pool")
    async def test_anonymize_cleans_comments(
        self, mock_repo_pool, mock_db_pool, mock_pool, mock_conn
    ):
        from app.services.user import anonymize_user

        mock_conn.execute.return_value = "UPDATE 1"
        mock_repo_pool.return_value = mock_pool
        mock_db_pool.return_value = mock_pool

        user_id = uuid.uuid4()
        await anonymize_user(user_id)

        execute_calls = [str(c) for c in mock_conn.execute.call_args_list]
        comment_calls = [c for c in execute_calls if "comments" in c and "is_deleted = true" in c]
        assert len(comment_calls) >= 1, "Should soft-delete user's comments"

    @patch("app.core.database.get_pool")
    @patch("app.repositories.user_repo.get_pool")
    async def test_anonymize_cleans_citations(
        self, mock_repo_pool, mock_db_pool, mock_pool, mock_conn
    ):
        from app.services.user import anonymize_user

        mock_conn.execute.return_value = "UPDATE 1"
        mock_repo_pool.return_value = mock_pool
        mock_db_pool.return_value = mock_pool

        user_id = uuid.uuid4()
        await anonymize_user(user_id)

        execute_calls = [str(c) for c in mock_conn.execute.call_args_list]
        citation_calls = [c for c in execute_calls if "post_citations" in c]
        assert len(citation_calls) >= 2, "Should delete both citing and cited references"

    @patch("app.core.database.get_pool")
    @patch("app.repositories.user_repo.get_pool")
    async def test_anonymize_cleans_sig_memberships(
        self, mock_repo_pool, mock_db_pool, mock_pool, mock_conn
    ):
        from app.services.user import anonymize_user

        mock_conn.execute.return_value = "UPDATE 1"
        mock_repo_pool.return_value = mock_pool
        mock_db_pool.return_value = mock_pool

        user_id = uuid.uuid4()
        await anonymize_user(user_id)

        execute_calls = [str(c) for c in mock_conn.execute.call_args_list]
        sig_calls = [c for c in execute_calls if "sig_members" in c]
        assert len(sig_calls) >= 1, "Should delete SIG memberships"

    @patch("app.core.database.get_pool")
    @patch("app.repositories.user_repo.get_pool")
    async def test_anonymize_cleans_notifications(
        self, mock_repo_pool, mock_db_pool, mock_pool, mock_conn
    ):
        from app.services.user import anonymize_user

        mock_conn.execute.return_value = "UPDATE 1"
        mock_repo_pool.return_value = mock_pool
        mock_db_pool.return_value = mock_pool

        user_id = uuid.uuid4()
        await anonymize_user(user_id)

        execute_calls = [str(c) for c in mock_conn.execute.call_args_list]
        notif_calls = [c for c in execute_calls if "notifications" in c]
        assert len(notif_calls) >= 1, "Should delete notifications"

    @patch("app.core.database.get_pool")
    @patch("app.repositories.user_repo.get_pool")
    async def test_anonymize_cleans_form_responses(
        self, mock_repo_pool, mock_db_pool, mock_pool, mock_conn
    ):
        from app.services.user import anonymize_user

        mock_conn.execute.return_value = "UPDATE 1"
        mock_repo_pool.return_value = mock_pool
        mock_db_pool.return_value = mock_pool

        user_id = uuid.uuid4()
        await anonymize_user(user_id)

        execute_calls = [str(c) for c in mock_conn.execute.call_args_list]
        form_calls = [c for c in execute_calls if "form_responses" in c]
        assert len(form_calls) >= 1, "Should delete form responses"

    @patch("app.core.database.get_pool")
    @patch("app.repositories.user_repo.get_pool")
    async def test_anonymize_cleans_friendships(
        self, mock_repo_pool, mock_db_pool, mock_pool, mock_conn
    ):
        from app.services.user import anonymize_user

        mock_conn.execute.return_value = "UPDATE 1"
        mock_repo_pool.return_value = mock_pool
        mock_db_pool.return_value = mock_pool

        user_id = uuid.uuid4()
        await anonymize_user(user_id)

        execute_calls = [str(c) for c in mock_conn.execute.call_args_list]
        friend_calls = [c for c in execute_calls if "friendships" in c]
        assert len(friend_calls) >= 1, "Should delete friendships"

    @patch("app.core.database.get_pool")
    @patch("app.repositories.user_repo.get_pool")
    async def test_anonymize_cleans_follows(
        self, mock_repo_pool, mock_db_pool, mock_pool, mock_conn
    ):
        from app.services.user import anonymize_user

        mock_conn.execute.return_value = "UPDATE 1"
        mock_repo_pool.return_value = mock_pool
        mock_db_pool.return_value = mock_pool

        user_id = uuid.uuid4()
        await anonymize_user(user_id)

        execute_calls = [str(c) for c in mock_conn.execute.call_args_list]
        follow_calls = [c for c in execute_calls if "follows" in c]
        assert len(follow_calls) >= 1, "Should delete follows"

    @patch("app.core.database.get_pool")
    @patch("app.repositories.user_repo.get_pool")
    async def test_anonymize_cleans_blocks(
        self, mock_repo_pool, mock_db_pool, mock_pool, mock_conn
    ):
        from app.services.user import anonymize_user

        mock_conn.execute.return_value = "UPDATE 1"
        mock_repo_pool.return_value = mock_pool
        mock_db_pool.return_value = mock_pool

        user_id = uuid.uuid4()
        await anonymize_user(user_id)

        execute_calls = [str(c) for c in mock_conn.execute.call_args_list]
        block_calls = [c for c in execute_calls if "blocks" in c]
        assert len(block_calls) >= 1, "Should delete blocks"

    @patch("app.core.database.get_pool")
    @patch("app.repositories.user_repo.get_pool")
    async def test_anonymize_uses_transaction(
        self, mock_repo_pool, mock_db_pool, mock_pool, mock_conn
    ):
        from app.services.user import anonymize_user

        mock_conn.execute.return_value = "UPDATE 1"
        mock_repo_pool.return_value = mock_pool
        mock_db_pool.return_value = mock_pool

        await anonymize_user(uuid.uuid4())

        # Verify transaction was used
        mock_conn.transaction.assert_called_once()

    @patch("app.core.database.get_pool")
    @patch("app.repositories.user_repo.get_pool")
    async def test_anonymize_not_found_skips_cleanup(
        self, mock_repo_pool, mock_db_pool, mock_pool, mock_conn
    ):
        from app.services.user import anonymize_user

        # anonymize returns False (user not found) — repo execute returns "UPDATE 0"
        mock_conn.execute.return_value = "UPDATE 0"
        mock_conn.fetchrow.return_value = None
        mock_repo_pool.return_value = mock_pool
        mock_db_pool.return_value = mock_pool

        result = await anonymize_user(uuid.uuid4())
        assert result["anonymized"] is False

        # Transaction should NOT be started since anonymize returned False
        mock_conn.transaction.assert_not_called()


# ── D2: SIG soft_delete cascade cleanup ─────────────────────────────


class TestSigSoftDeleteCascade:
    """Verify that SIG soft_delete cleans up all child records."""

    @patch("app.repositories.sig_repo.get_pool")
    async def test_soft_delete_cleans_form_responses(self, mock_get_pool, mock_pool, mock_conn):
        from app.repositories.sig_repo import soft_delete

        mock_conn.execute.return_value = "UPDATE 1"
        mock_get_pool.return_value = mock_pool

        sig_id = uuid.uuid4()
        result = await soft_delete(sig_id)
        assert result is True

        execute_calls = [str(c) for c in mock_conn.execute.call_args_list]
        fr_calls = [c for c in execute_calls if "form_responses" in c]
        assert len(fr_calls) >= 1, "Should delete form responses for SIG forms"

    @patch("app.repositories.sig_repo.get_pool")
    async def test_soft_delete_cleans_citations(self, mock_get_pool, mock_pool, mock_conn):
        from app.repositories.sig_repo import soft_delete

        mock_conn.execute.return_value = "UPDATE 1"
        mock_get_pool.return_value = mock_pool

        sig_id = uuid.uuid4()
        await soft_delete(sig_id)

        execute_calls = [str(c) for c in mock_conn.execute.call_args_list]
        citation_calls = [c for c in execute_calls if "post_citations" in c]
        assert len(citation_calls) >= 1, "Should delete post citations for SIG posts"

    @patch("app.repositories.sig_repo.get_pool")
    async def test_soft_delete_cleans_comment_votes(self, mock_get_pool, mock_pool, mock_conn):
        from app.repositories.sig_repo import soft_delete

        mock_conn.execute.return_value = "UPDATE 1"
        mock_get_pool.return_value = mock_pool

        sig_id = uuid.uuid4()
        await soft_delete(sig_id)

        execute_calls = [str(c) for c in mock_conn.execute.call_args_list]
        vote_calls = [c for c in execute_calls if "comment_votes" in c]
        assert len(vote_calls) >= 1, "Should delete comment votes on SIG post comments"

    @patch("app.repositories.sig_repo.get_pool")
    async def test_soft_delete_cleans_comments(self, mock_get_pool, mock_pool, mock_conn):
        from app.repositories.sig_repo import soft_delete

        mock_conn.execute.return_value = "UPDATE 1"
        mock_get_pool.return_value = mock_pool

        sig_id = uuid.uuid4()
        await soft_delete(sig_id)

        execute_calls = [str(c) for c in mock_conn.execute.call_args_list]
        comment_calls = [c for c in execute_calls if "comments" in c and "is_deleted = true" in c]
        assert len(comment_calls) >= 1, "Should soft-delete comments on SIG posts"

    @patch("app.repositories.sig_repo.get_pool")
    async def test_soft_delete_not_found_returns_false(self, mock_get_pool, mock_pool, mock_conn):
        from app.repositories.sig_repo import soft_delete

        mock_conn.execute.return_value = "UPDATE 0"
        mock_get_pool.return_value = mock_pool

        sig_id = uuid.uuid4()
        result = await soft_delete(sig_id)
        assert result is False

    @patch("app.repositories.sig_repo.get_pool")
    async def test_soft_delete_order_children_before_parents(
        self, mock_get_pool, mock_pool, mock_conn
    ):
        """Verify that child records are deleted before parent records are soft-deleted."""
        from app.repositories.sig_repo import soft_delete

        mock_conn.execute.return_value = "UPDATE 1"
        mock_get_pool.return_value = mock_pool

        sig_id = uuid.uuid4()
        await soft_delete(sig_id)

        # Collect the SQL statements in order
        sql_stmts = [str(c.args[0]) if c.args else "" for c in mock_conn.execute.call_args_list]

        # Find indices
        form_resp_idx = None
        posts_soft_idx = None
        members_idx = None
        for i, s in enumerate(sql_stmts):
            if "form_responses" in s:
                form_resp_idx = i
            if "posts" in s and "is_deleted = true" in s and "sig_id" in s:
                posts_soft_idx = i
            if "sig_members" in s and ("DELETE" in s or "is_deleted = true" in s):
                members_idx = i

        assert form_resp_idx is not None, "form_responses cleanup should be present"
        assert posts_soft_idx is not None, "posts soft-delete should be present"
        assert members_idx is not None, "sig_members cleanup should be present"
        # form_responses before posts, posts before members
        assert form_resp_idx < posts_soft_idx, "form_responses should be cleaned before posts"
        assert posts_soft_idx < members_idx, "posts should be soft-deleted before members removed"


# ── B1: SIG posts viewer_id ─────────────────────────────────────────


class TestSigPostsViewerId:
    """Verify that GET /sigs/{id}/posts passes viewer_id to list_posts."""

    @pytest.mark.anyio
    async def test_sig_posts_passes_viewer_id(self, client):
        """GET /sigs/{id}/posts should pass viewer_id=current_user['sub']."""
        from app.core.deps import get_current_user
        from app.main import app

        user_id = str(uuid.uuid4())
        sig_id = uuid.uuid4()

        app.dependency_overrides[get_current_user] = lambda: {
            "sub": user_id,
            "role": "MEMBER",
            "jti": "jti-test",
        }

        mock_list = AsyncMock(
            return_value={"posts": [], "total": 0, "total_pages": 0},
        )

        try:
            with patch(f"{_EP}.list_posts", mock_list):
                resp = await client.get(
                    f"/api/v1/sigs/{sig_id}/posts",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200

                # Verify list_posts was called with viewer_id
                mock_list.assert_called_once()
                call_kwargs = mock_list.call_args
                assert call_kwargs.kwargs.get("viewer_id") == user_id or (
                    len(call_kwargs.args) == 0
                    and "viewer_id" in str(call_kwargs)
                    and user_id in str(call_kwargs)
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.anyio
    async def test_sig_posts_viewer_id_in_kwargs(self, client):
        """Explicitly check that viewer_id keyword is passed."""
        from app.core.deps import get_current_user
        from app.main import app

        user_id = str(uuid.uuid4())
        sig_id = uuid.uuid4()

        app.dependency_overrides[get_current_user] = lambda: {
            "sub": user_id,
            "role": "MEMBER",
            "jti": "jti-test",
        }

        mock_list = AsyncMock(
            return_value={"posts": [], "total": 0, "total_pages": 0},
        )

        try:
            with patch(f"{_EP}.list_posts", mock_list):
                await client.get(
                    f"/api/v1/sigs/{sig_id}/posts",
                    headers={"Authorization": "Bearer fake"},
                )

                _, kwargs = mock_list.call_args
                assert "viewer_id" in kwargs, "viewer_id must be passed to list_posts"
                assert kwargs["viewer_id"] == user_id
        finally:
            app.dependency_overrides.pop(get_current_user, None)
