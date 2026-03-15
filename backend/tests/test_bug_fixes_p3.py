"""Tests for P3 bug fixes (bugs 9-14).

Bug 9:  reaction_helpers passes string for UUID column
Bug 10: update_post rejects admin editing others' posts
Bug 11: soft_delete_form permission check not in same transaction
Bug 12: about.py avatar proxy only follows one redirect level
Bug 13: SIG update endpoint TOCTOU on permission check
Bug 14: guest_login discards display_name
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Bug 9: reaction_helpers UUID conversion ─────────────────────────────


class TestReactionHelperUUIDConversion:
    """Verify toggle_reaction_jsonb converts string row_id to uuid.UUID."""

    @pytest.mark.asyncio
    async def test_string_row_id_converted_to_uuid(self):
        """When row_id is a plain string, it should be converted to UUID before query."""
        from app.repositories.reaction_helpers import toggle_reaction_jsonb

        fake_conn = AsyncMock()
        row_uuid = uuid.uuid4()
        row_id_str = str(row_uuid)
        fake_conn.fetchrow.return_value = {"reactions": None}

        await toggle_reaction_jsonb(fake_conn, "posts", row_id_str, "user1", "like")

        # The SELECT should have been called with a UUID object, not a string
        call_args = fake_conn.fetchrow.call_args
        passed_id = call_args[0][1]
        assert isinstance(passed_id, uuid.UUID)
        assert passed_id == row_uuid

    @pytest.mark.asyncio
    async def test_uuid_row_id_stays_uuid(self):
        """When row_id is already a UUID object, it should remain a UUID."""
        from app.repositories.reaction_helpers import toggle_reaction_jsonb

        fake_conn = AsyncMock()
        row_id = uuid.uuid4()
        fake_conn.fetchrow.return_value = {"reactions": None}

        await toggle_reaction_jsonb(fake_conn, "posts", row_id, "user1", "like")

        call_args = fake_conn.fetchrow.call_args
        passed_id = call_args[0][1]
        assert isinstance(passed_id, uuid.UUID)
        assert passed_id == row_id

    @pytest.mark.asyncio
    async def test_update_also_uses_uuid(self):
        """The UPDATE statement should also receive a UUID, not a string."""
        from app.repositories.reaction_helpers import toggle_reaction_jsonb

        fake_conn = AsyncMock()
        row_uuid = uuid.uuid4()
        fake_conn.fetchrow.return_value = {"reactions": None}

        await toggle_reaction_jsonb(fake_conn, "comments", str(row_uuid), "user1", "like")

        # For non-"posts" table, execute is called once (the UPDATE)
        update_call = fake_conn.execute.call_args_list[0]
        passed_id = update_call[0][2]
        assert isinstance(passed_id, uuid.UUID)
        assert passed_id == row_uuid

    @pytest.mark.asyncio
    async def test_invalid_uuid_string_raises(self):
        """An invalid UUID string should raise ValueError immediately."""
        from app.repositories.reaction_helpers import toggle_reaction_jsonb

        fake_conn = AsyncMock()

        with pytest.raises(ValueError):
            await toggle_reaction_jsonb(fake_conn, "posts", "not-a-uuid", "user1", "like")


# ── Bug 10: update_post allows admin to edit others' posts ──────────────


def _make_post_row(user_id=None, version=1):
    """Helper to create a mock post row dict."""
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
        "like_count": 0,
        "is_pinned": False,
        "view_count": 0,
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


class TestUpdatePostAdminEdit:
    """Bug 10: ADMIN and SUPER_ADMIN should be able to edit any post."""

    @patch("app.services.post.get_pool")
    async def test_admin_can_edit_others_post(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.post import update_post

        owner_id = str(uuid.uuid4())
        admin_id = str(uuid.uuid4())
        post_id = uuid.uuid4()

        current_row = _make_post_row(user_id=owner_id, version=1)
        updated_row = _make_post_row(user_id=owner_id, version=2)
        updated_row["title"] = "Admin Updated"
        # fetchrow calls: find_for_update returns current, update_in_transaction returns updated
        # insert_history uses conn.execute (not fetchrow)
        mock_conn.fetchrow = AsyncMock(side_effect=[current_row, updated_row])
        mock_conn.execute = AsyncMock()
        mock_get_pool.return_value = mock_pool

        result = await update_post(post_id, admin_id, title="Admin Updated", caller_role="ADMIN")
        assert result is not None

    @patch("app.services.post.get_pool")
    async def test_super_admin_can_edit_others_post(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.post import update_post

        owner_id = str(uuid.uuid4())
        admin_id = str(uuid.uuid4())
        post_id = uuid.uuid4()

        current_row = _make_post_row(user_id=owner_id, version=1)
        updated_row = _make_post_row(user_id=owner_id, version=2)
        # fetchrow calls: find_for_update returns current, update_in_transaction returns updated
        mock_conn.fetchrow = AsyncMock(side_effect=[current_row, updated_row])
        mock_conn.execute = AsyncMock()
        mock_get_pool.return_value = mock_pool

        result = await update_post(post_id, admin_id, title="Updated", caller_role="SUPER_ADMIN")
        assert result is not None

    @patch("app.services.post.get_pool")
    async def test_member_cannot_edit_others_post(self, mock_get_pool, mock_pool, mock_conn):
        from app.services.post import update_post

        owner_id = str(uuid.uuid4())
        other_id = str(uuid.uuid4())
        post_id = uuid.uuid4()

        current_row = _make_post_row(user_id=owner_id, version=1)
        mock_conn.fetchrow = AsyncMock(return_value=current_row)
        mock_get_pool.return_value = mock_pool

        with pytest.raises(PermissionError, match="only edit your own"):
            await update_post(post_id, other_id, title="Hacked", caller_role="MEMBER")

    @patch("app.services.post.get_pool")
    async def test_default_caller_role_is_member(self, mock_get_pool, mock_pool, mock_conn):
        """Without caller_role arg, non-owner should still be rejected."""
        from app.services.post import update_post

        owner_id = str(uuid.uuid4())
        other_id = str(uuid.uuid4())
        post_id = uuid.uuid4()

        current_row = _make_post_row(user_id=owner_id, version=1)
        mock_conn.fetchrow = AsyncMock(return_value=current_row)
        mock_get_pool.return_value = mock_pool

        with pytest.raises(PermissionError):
            await update_post(post_id, other_id, title="Test")


# ── Bug 11: soft_delete_form permission in same transaction ─────────────


class TestSoftDeleteFormTransaction:
    """Bug 11: Permission check and delete should be in the same transaction."""

    @patch("app.repositories.form_repo.get_pool")
    async def test_soft_delete_with_permission_authorized(
        self, mock_get_pool, mock_pool, mock_conn
    ):
        """Creator can delete their own form in a single transaction."""
        from app.repositories.form_repo import soft_delete_with_permission

        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        mock_conn.fetchrow.return_value = {
            "created_by": uuid.UUID(user_id),
            "banner_url": "/api/v1/files/content/forms/banners/test.png",
        }
        mock_get_pool.return_value = mock_pool

        deleted, banner_url = await soft_delete_with_permission(form_id, user_id, is_admin=False)
        assert deleted is True
        assert banner_url == "/api/v1/files/content/forms/banners/test.png"
        # Verify transaction was used
        mock_conn.transaction.assert_called_once()

    @patch("app.repositories.form_repo.get_pool")
    async def test_soft_delete_with_permission_admin_bypass(
        self, mock_get_pool, mock_pool, mock_conn
    ):
        """Admin can delete any form regardless of creator."""
        from app.repositories.form_repo import soft_delete_with_permission

        form_id = uuid.uuid4()
        creator_id = str(uuid.uuid4())
        admin_id = str(uuid.uuid4())

        mock_conn.fetchrow.return_value = {
            "created_by": uuid.UUID(creator_id),
            "banner_url": None,
        }
        mock_get_pool.return_value = mock_pool

        deleted, banner_url = await soft_delete_with_permission(form_id, admin_id, is_admin=True)
        assert deleted is True

    @patch("app.repositories.form_repo.get_pool")
    async def test_soft_delete_with_permission_unauthorized(
        self, mock_get_pool, mock_pool, mock_conn
    ):
        """Non-creator non-admin should get PermissionError."""
        from app.repositories.form_repo import soft_delete_with_permission

        form_id = uuid.uuid4()
        creator_id = str(uuid.uuid4())
        other_id = str(uuid.uuid4())

        mock_conn.fetchrow.return_value = {
            "created_by": uuid.UUID(creator_id),
            "banner_url": None,
        }
        mock_get_pool.return_value = mock_pool

        with pytest.raises(PermissionError, match="Only the form creator or admin"):
            await soft_delete_with_permission(form_id, other_id, is_admin=False)

    @patch("app.repositories.form_repo.get_pool")
    async def test_soft_delete_with_permission_not_found(self, mock_get_pool, mock_pool, mock_conn):
        """Non-existent form returns (False, None)."""
        from app.repositories.form_repo import soft_delete_with_permission

        mock_conn.fetchrow.return_value = None
        mock_get_pool.return_value = mock_pool

        deleted, banner_url = await soft_delete_with_permission(
            uuid.uuid4(), str(uuid.uuid4()), is_admin=False
        )
        assert deleted is False
        assert banner_url is None

    @patch("app.repositories.form_repo.get_pool")
    async def test_soft_delete_uses_for_update(self, mock_get_pool, mock_pool, mock_conn):
        """The SELECT query should include FOR UPDATE to prevent TOCTOU."""
        from app.repositories.form_repo import soft_delete_with_permission

        user_id = str(uuid.uuid4())
        mock_conn.fetchrow.return_value = {
            "created_by": uuid.UUID(user_id),
            "banner_url": None,
        }
        mock_get_pool.return_value = mock_pool

        await soft_delete_with_permission(uuid.uuid4(), user_id, is_admin=False)

        select_query = mock_conn.fetchrow.call_args[0][0]
        assert "FOR UPDATE" in select_query


# ── Bug 12: about.py avatar proxy multi-redirect ────────────────────────


class TestAvatarProxyRedirect:
    """Bug 12: Avatar proxy should follow multi-level redirects."""

    @pytest.mark.anyio
    async def test_avatar_proxy_uses_allow_redirects_true(self, client):
        """The requests.get call should use allow_redirects=True."""
        from app.api.v1.endpoints import about

        _EP = "app.api.v1.endpoints.about"

        def _override_auth(role="MEMBER"):
            from app.core.deps import get_current_user
            from app.main import app

            uid = str(uuid.uuid4())
            payload = {"sub": uid, "role": role, "jti": str(uuid.uuid4())}
            app.dependency_overrides[get_current_user] = lambda: payload
            return payload, uid

        contributor_id = str(uuid.uuid4())
        fake_contributor = {
            "id": uuid.UUID(contributor_id),
            "github_username": "testuser",
            "display_name": "Test User",
            "role": "Contributor",
            "display_order": 0,
            "created_at": datetime.now(timezone.utc),
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "image/png"}
        mock_response.content = b"\x89PNG\r\n\x1a\n"  # PNG header

        try:
            _override_auth("MEMBER")
            # Clear any stale cache entries
            async with about._cache_lock:
                about._avatar_cache.clear()
                about._cache_total_bytes = 0

            with (
                patch(
                    f"{_EP}.contributor_service.get_contributor",
                    new_callable=AsyncMock,
                    return_value=fake_contributor,
                ),
                patch(f"{_EP}._requests.get", return_value=mock_response) as mock_get,
            ):
                resp = await client.get(
                    f"/api/v1/about/contributors/{contributor_id}/avatar",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                # Verify allow_redirects=True was used
                mock_get.assert_called_once()
                call_kwargs = mock_get.call_args
                assert call_kwargs[1].get("allow_redirects") is True
        finally:
            from app.main import app

            app.dependency_overrides.clear()


# ── Bug 13: SIG update TOCTOU ───────────────────────────────────────────


class TestSigUpdateTOCTOU:
    """Bug 13: SIG update permission check should be inside the transaction."""

    @patch("app.services.sig.get_pool")
    @patch("app.repositories.sig_repo.get_pool")
    async def test_update_sig_permission_check_in_transaction(
        self, mock_repo_pool, mock_svc_pool, mock_pool, mock_conn
    ):
        """Permission check for SIG member role should happen inside the transaction."""
        from app.services.sig import update_sig

        sig_id = uuid.uuid4()
        caller_id = str(uuid.uuid4())

        # SIG member role check returns "MEMBER" (not ADMIN) — should be rejected
        mock_conn.fetchrow = AsyncMock(return_value={"role": "MEMBER"})
        mock_svc_pool.return_value = mock_pool
        mock_repo_pool.return_value = mock_pool

        with pytest.raises(PermissionError, match="Not authorized"):
            await update_sig(
                sig_id,
                name="Updated",
                caller_id=caller_id,
                caller_role="MEMBER",
            )

    @patch("app.services.sig.get_pool")
    async def test_update_sig_global_admin_skips_sig_role_check(
        self, mock_svc_pool, mock_pool, mock_conn
    ):
        """Global ADMIN should bypass SIG role check."""
        from app.services.sig import update_sig

        sig_id = uuid.uuid4()
        caller_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        sig_row = {
            "id": sig_id,
            "name": "Test SIG",
            "description": "Desc",
            "created_by": uuid.uuid4(),
            "member_count": 1,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "creator_display_name": "Creator",
        }
        # First fetchrow: current SIG; second fetchrow: updated SIG
        mock_conn.fetchrow = AsyncMock(side_effect=[sig_row, sig_row])
        mock_svc_pool.return_value = mock_pool

        result = await update_sig(
            sig_id,
            name="Updated",
            caller_id=caller_id,
            caller_role="ADMIN",
        )
        assert result is not None

    @patch("app.services.sig.get_pool")
    @patch("app.repositories.sig_repo.get_pool")
    async def test_update_sig_sig_admin_allowed(
        self, mock_repo_pool, mock_svc_pool, mock_pool, mock_conn
    ):
        """SIG ADMIN (not global admin) should be allowed to update."""
        from app.services.sig import update_sig

        sig_id = uuid.uuid4()
        caller_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        sig_row = {
            "id": sig_id,
            "name": "Test SIG",
            "description": "Desc",
            "created_by": uuid.uuid4(),
            "member_count": 1,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "creator_display_name": "Creator",
        }
        # First fetchrow: SIG role check returns ADMIN; second: current; third: updated
        mock_conn.fetchrow = AsyncMock(side_effect=[{"role": "ADMIN"}, sig_row, sig_row])
        mock_svc_pool.return_value = mock_pool
        mock_repo_pool.return_value = mock_pool

        result = await update_sig(
            sig_id,
            name="Updated",
            caller_id=caller_id,
            caller_role="MEMBER",
        )
        assert result is not None

    @patch("app.services.sig.get_pool")
    async def test_update_sig_no_caller_info_skips_permission(
        self, mock_svc_pool, mock_pool, mock_conn
    ):
        """Without caller info, permission check is skipped (backward compat)."""
        from app.services.sig import update_sig

        sig_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        sig_row = {
            "id": sig_id,
            "name": "Test SIG",
            "description": "Desc",
            "created_by": uuid.uuid4(),
            "member_count": 1,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "creator_display_name": "Creator",
        }
        mock_conn.fetchrow = AsyncMock(side_effect=[sig_row, sig_row])
        mock_svc_pool.return_value = mock_pool

        result = await update_sig(sig_id, name="Updated")
        assert result is not None


# ── Bug 14: guest_login stores display_name in Redis ────────────────────


class TestGuestDisplayNameStored:
    """Bug 14: guest_login should store display_name in Redis."""

    @patch("app.services.auth.create_session")
    @patch("app.services.auth.get_redis")
    async def test_guest_login_stores_display_name(self, mock_get_redis, mock_create_session):
        from app.services.auth import guest_login

        async def _empty_scan(*a, **kw):
            return
            yield  # noqa

        redis = AsyncMock()
        redis.eval = AsyncMock(return_value=5)
        mock_get_redis.return_value = redis
        mock_create_session.return_value = ("token-guest", 2700)

        result = await guest_login("Test Guest")
        assert result is not None

        # Verify display_name was stored in Redis
        set_calls = redis.set.call_args_list
        display_name_calls = [c for c in set_calls if "guest:display_name:" in str(c[0][0])]
        assert len(display_name_calls) == 1
        call = display_name_calls[0]
        assert call[0][1] == "Test Guest"
        # TTL should match session TTL
        assert call[1]["ex"] == 2700

    @patch("app.services.auth.create_session")
    @patch("app.services.auth.get_redis")
    async def test_guest_display_name_key_contains_guest_id(
        self, mock_get_redis, mock_create_session
    ):
        """The Redis key should contain the guest's UUID."""
        from app.services.auth import guest_login

        redis = AsyncMock()
        redis.eval = AsyncMock(return_value=1)
        mock_get_redis.return_value = redis
        mock_create_session.return_value = ("tok", 2700)

        await guest_login("Alice")

        set_calls = redis.set.call_args_list
        display_name_calls = [c for c in set_calls if "guest:display_name:" in str(c[0][0])]
        assert len(display_name_calls) == 1
        key = display_name_calls[0][0][0]
        # Extract and validate the UUID part
        parts = key.split(":")
        assert len(parts) == 3
        uuid.UUID(parts[2])  # Should not raise

    @patch("app.services.auth.get_redis")
    async def test_guest_login_limit_reached_no_display_name_stored(self, mock_get_redis):
        """When guest limit is reached, display_name should NOT be stored."""
        from app.services.auth import guest_login

        redis = AsyncMock()
        redis.eval = AsyncMock(return_value=-1)
        mock_get_redis.return_value = redis

        result = await guest_login("Over Limit Guest")
        assert result is None

        # No display_name key should have been set
        set_calls = redis.set.call_args_list
        display_name_calls = [c for c in set_calls if "guest:display_name:" in str(c[0][0])]
        assert len(display_name_calls) == 0
