"""Tests for P0/P1 bug fixes:
- Bug 1 (P0): bulk_change_role missing SUPER_ADMIN protection
- Bug 2 (P1): Guest counter drift — sync_guest_counter + Celery task
- Bug 3 (P1): like_count not updated by toggle_reaction
"""

import json
import sys
import types
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =========================================================================
# Bug 1: bulk_change_role SUPER_ADMIN protection
# =========================================================================

_USER_SVC = "app.services.user"


class TestBulkChangeRoleSuperAdminProtection:
    """Verify bulk_change_role cannot remove the last SUPER_ADMIN."""

    @pytest.mark.anyio
    async def test_bulk_demote_last_super_admin_raises(self, mock_pool, mock_conn):
        """Bulk demoting all SUPER_ADMINs when no others exist should raise."""
        from app.services.user import bulk_change_role

        sa_id = uuid.uuid4()

        with (
            patch(
                f"{_USER_SVC}.user_repo.count_super_admins_excluding",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch("app.core.database.get_pool", return_value=mock_pool),
        ):
            with pytest.raises(ValueError, match="last Super Admin"):
                await bulk_change_role([sa_id], "ADMIN")

    @pytest.mark.anyio
    async def test_bulk_demote_when_other_super_admins_exist(self, mock_pool, mock_conn):
        """Bulk demoting should succeed when other SUPER_ADMINs remain."""
        from app.services.user import bulk_change_role

        sa_id = uuid.uuid4()

        with (
            patch(
                f"{_USER_SVC}.user_repo.count_super_admins_excluding",
                new_callable=AsyncMock,
                return_value=1,
            ),
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch(
                f"{_USER_SVC}.user_repo.bulk_update_role",
                new_callable=AsyncMock,
                return_value=1,
            ),
        ):
            count = await bulk_change_role([sa_id], "ADMIN")
            assert count == 1

    @pytest.mark.anyio
    async def test_bulk_promote_to_super_admin_skips_check(self, mock_pool, mock_conn):
        """Promoting to SUPER_ADMIN should not trigger the protection check."""
        from app.services.user import bulk_change_role

        user_id = uuid.uuid4()
        mock_count = AsyncMock()

        with (
            patch(
                f"{_USER_SVC}.user_repo.count_super_admins_excluding",
                mock_count,
            ),
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch(
                f"{_USER_SVC}.user_repo.bulk_update_role",
                new_callable=AsyncMock,
                return_value=1,
            ),
        ):
            count = await bulk_change_role([user_id], "SUPER_ADMIN")
            assert count == 1
            # The protection check should never be called for promotions
            mock_count.assert_not_called()

    @pytest.mark.anyio
    async def test_bulk_change_role_empty_list_skips_check(self, mock_pool, mock_conn):
        """Empty user list should skip the protection check."""
        from app.services.user import bulk_change_role

        mock_count = AsyncMock()

        with (
            patch(
                f"{_USER_SVC}.user_repo.count_super_admins_excluding",
                mock_count,
            ),
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch(
                f"{_USER_SVC}.user_repo.bulk_update_role",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            count = await bulk_change_role([], "ADMIN")
            assert count == 0
            mock_count.assert_not_called()


# =========================================================================
# Bug 2: Guest counter drift — sync_guest_counter + Celery task
# =========================================================================

_AUTH_SVC = "app.services.auth"


class TestSyncGuestCounter:
    """Verify sync_guest_counter reconciles counter with session keys."""

    @pytest.mark.anyio
    async def test_sync_counts_session_keys(self, mock_redis):
        """sync_guest_counter should count session:GUEST:* keys and set counter."""
        from app.services.auth import sync_guest_counter

        # Simulate 3 guest session keys
        async def fake_scan_iter(*args, **kwargs):
            for key in ["session:GUEST:a", "session:GUEST:b", "session:GUEST:c"]:
                yield key

        mock_redis.scan_iter = fake_scan_iter

        with patch(f"{_AUTH_SVC}.get_redis", return_value=mock_redis):
            await sync_guest_counter()

        # Should set the counter to 3
        mock_redis.set.assert_called_once_with("meta:guest_counter", 3)

    @pytest.mark.anyio
    async def test_sync_sets_zero_when_no_sessions(self, mock_redis):
        """sync_guest_counter should set counter to 0 when no guest sessions exist."""
        from app.services.auth import sync_guest_counter

        async def fake_scan_iter(*args, **kwargs):
            return
            yield  # make it an async generator

        mock_redis.scan_iter = fake_scan_iter

        with patch(f"{_AUTH_SVC}.get_redis", return_value=mock_redis):
            await sync_guest_counter()

        mock_redis.set.assert_called_once_with("meta:guest_counter", 0)


class TestSyncGuestCounterCeleryTask:
    """Verify the Celery beat task for guest counter sync."""

    @pytest.fixture(autouse=True)
    def _celery_modules(self):
        """Inject fake celery modules so lazy imports succeed."""
        celery_mod = types.ModuleType("celery")
        celery_result_mod = types.ModuleType("celery.result")
        celery_mod.result = celery_result_mod
        celery_mod.shared_task = lambda **kw: (lambda fn: fn)

        celery_app_mod = types.ModuleType("app.celery_app")
        mock_celery_app = MagicMock()
        mock_celery_app.task = lambda *a, **kw: (lambda fn: fn)
        celery_app_mod.celery = mock_celery_app

        saved = {}
        for key in ("celery", "celery.result", "app.celery_app"):
            saved[key] = sys.modules.get(key)

        sys.modules["celery"] = celery_mod
        sys.modules["celery.result"] = celery_result_mod
        sys.modules["app.celery_app"] = celery_app_mod

        yield

        for key, val in saved.items():
            if val is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = val

    def test_sync_guest_counter_task_calls_sync(self):
        """The Celery task should call sync_guest_counter and return status."""
        mock_sync = AsyncMock()

        with patch(f"{_AUTH_SVC}.sync_guest_counter", mock_sync):
            # Force reimport to pick up mocked celery decorator
            if "app.tasks.cleanup" in sys.modules:
                del sys.modules["app.tasks.cleanup"]
            from app.tasks.cleanup import sync_guest_counter_task

            result = sync_guest_counter_task(MagicMock())

        assert result == {"status": "synced"}


# =========================================================================
# Bug 3: like_count not updated by toggle_reaction
# =========================================================================

_REACTION_HELPERS = "app.repositories.reaction_helpers"


class TestToggleReactionLikeCount:
    """Verify toggle_reaction_jsonb updates like_count for posts."""

    @pytest.mark.anyio
    async def test_like_reaction_updates_like_count(self):
        """Adding a like reaction should set like_count to 1 on posts."""
        conn = AsyncMock()
        post_id = str(uuid.uuid4())
        post_uuid = uuid.UUID(post_id)
        user_id = str(uuid.uuid4())

        # Row has no reactions initially
        conn.fetchrow = AsyncMock(return_value={"reactions": "{}"})
        conn.execute = AsyncMock()

        from app.repositories.reaction_helpers import toggle_reaction_jsonb

        result = await toggle_reaction_jsonb(conn, "posts", post_id, user_id, "like")

        assert result == {"like": [user_id]}
        # Should have 2 execute calls: update reactions + update like_count
        assert conn.execute.call_count == 2
        # Second call should update like_count
        like_count_call = conn.execute.call_args_list[1]
        assert like_count_call[0][0] == "UPDATE posts SET like_count = $1 WHERE id = $2"
        assert like_count_call[0][1] == 1
        assert like_count_call[0][2] == post_uuid

    @pytest.mark.anyio
    async def test_unlike_reaction_sets_like_count_zero(self):
        """Removing the last like reaction should set like_count to 0."""
        conn = AsyncMock()
        post_id = str(uuid.uuid4())
        post_uuid = uuid.UUID(post_id)
        user_id = str(uuid.uuid4())

        # Row already has a like from this user
        conn.fetchrow = AsyncMock(return_value={"reactions": json.dumps({"like": [user_id]})})
        conn.execute = AsyncMock()

        from app.repositories.reaction_helpers import toggle_reaction_jsonb

        result = await toggle_reaction_jsonb(conn, "posts", post_id, user_id, "like")

        # Like list should be removed (empty lists are deleted)
        assert "like" not in result
        # like_count should be set to 0
        assert conn.execute.call_count == 2
        like_count_call = conn.execute.call_args_list[1]
        assert like_count_call[0][1] == 0

    @pytest.mark.anyio
    async def test_heart_reaction_does_not_update_like_count(self):
        """Non-like reactions should still not affect like_count."""
        conn = AsyncMock()
        post_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        conn.fetchrow = AsyncMock(return_value={"reactions": "{}"})
        conn.execute = AsyncMock()

        from app.repositories.reaction_helpers import toggle_reaction_jsonb

        result = await toggle_reaction_jsonb(conn, "posts", post_id, user_id, "heart")

        assert result == {"heart": [user_id]}
        # Should have 2 calls: update reactions + update like_count (0 likes)
        assert conn.execute.call_count == 2
        like_count_call = conn.execute.call_args_list[1]
        assert like_count_call[0][1] == 0  # no likes

    @pytest.mark.anyio
    async def test_comment_reaction_skips_like_count(self):
        """Reactions on comments table should NOT update like_count."""
        conn = AsyncMock()
        comment_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        conn.fetchrow = AsyncMock(return_value={"reactions": "{}"})
        conn.execute = AsyncMock()

        from app.repositories.reaction_helpers import toggle_reaction_jsonb

        result = await toggle_reaction_jsonb(conn, "comments", comment_id, user_id, "like")

        assert result == {"like": [user_id]}
        # Should have only 1 execute call (update reactions), no like_count update
        assert conn.execute.call_count == 1

    @pytest.mark.anyio
    async def test_multiple_likes_counted_correctly(self):
        """like_count should reflect the number of users who liked."""
        conn = AsyncMock()
        post_id = str(uuid.uuid4())
        post_uuid = uuid.UUID(post_id)
        user_a = str(uuid.uuid4())
        user_b = str(uuid.uuid4())
        new_user = str(uuid.uuid4())

        # Already has 2 likes
        existing = {"like": [user_a, user_b], "heart": [user_a]}
        conn.fetchrow = AsyncMock(return_value={"reactions": json.dumps(existing)})
        conn.execute = AsyncMock()

        from app.repositories.reaction_helpers import toggle_reaction_jsonb

        result = await toggle_reaction_jsonb(conn, "posts", post_id, new_user, "like")

        assert len(result["like"]) == 3
        like_count_call = conn.execute.call_args_list[1]
        assert like_count_call[0][1] == 3
