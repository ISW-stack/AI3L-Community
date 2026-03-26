"""Tests for functional bug fixes F-41 through F-58.

F-41: Guest counter initialization TOCTOU race (setnx)
F-42: asyncpg.execute() string comparison (endswith instead of ==)
F-43: Form response permission defense-in-depth (guest_allowed param)
F-44: get_dm_friends_only returns None for non-existent users
F-45: update_my_profile validates non-clearable fields
F-57: Missing explicit sub None check in co-author invitations
F-58: Form responses auth timing oracle (return 404 instead of 403)
"""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Module path aliases ──────────────────────────────────────────────────

_AUTH_SVC = "app.services.auth"
_ADMIN_EP = "app.api.v1.endpoints.admin"
_USERS_EP = "app.api.v1.endpoints.users"
_FORMS_EP = "app.api.v1.endpoints.forms"
_USER_SVC = "app.services.user"
_DM_REPO = "app.repositories.dm_repo"
_FORM_REPO = "app.repositories.form_repo"

_USER_ID = str(uuid.uuid4())
_FORM_ID = uuid.uuid4()
_NOW = datetime.now(timezone.utc)


# ── Helpers ──────────────────────────────────────────────────────────────


def _override_auth(role="MEMBER", user_id=None):
    from app.core.deps import get_current_user
    from app.main import app

    uid = user_id or _USER_ID
    payload = {"sub": uid, "role": role, "jti": str(uuid.uuid4())}
    app.dependency_overrides[get_current_user] = lambda: payload
    return payload, uid


def _clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()


# ── F-41: Guest counter initialization TOCTOU race ───────────────────────


class TestF41GuestCounterTOCTOU:
    """sync_guest_counter and _get_guest_count use SET NX for atomic init."""

    @pytest.mark.anyio
    async def test_get_guest_count_uses_setnx_on_init(self):
        """_get_guest_count uses SET NX to prevent race on first init."""
        mock_redis = AsyncMock()
        # First get returns None (not initialized), then after setnx returns "0"
        mock_redis.get = AsyncMock(side_effect=[None, b"0"])
        mock_redis.set = AsyncMock()
        mock_redis.scan_iter = MagicMock(return_value=AsyncIterMock([]))

        with patch(f"{_AUTH_SVC}.get_redis", return_value=mock_redis):
            from app.services.auth import _get_guest_count

            count = await _get_guest_count()

        assert count == 0
        # Verify set was called with nx=True
        mock_redis.set.assert_called_once()
        call_kwargs = mock_redis.set.call_args
        assert call_kwargs[1].get("nx") is True or (
            len(call_kwargs[0]) >= 2 and call_kwargs[1].get("nx") is True
        )

    @pytest.mark.anyio
    async def test_get_guest_count_returns_existing_value(self):
        """_get_guest_count returns existing counter without setnx."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=b"5")

        with patch(f"{_AUTH_SVC}.get_redis", return_value=mock_redis):
            from app.services.auth import _get_guest_count

            count = await _get_guest_count()

        assert count == 5
        # Should not call set at all
        mock_redis.set.assert_not_called()

    @pytest.mark.anyio
    async def test_get_guest_count_counts_sessions_on_init(self):
        """_get_guest_count scans session keys when counter is None."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=[None, b"3"])
        mock_redis.set = AsyncMock()
        # Simulate 3 guest sessions
        mock_redis.scan_iter = MagicMock(
            return_value=AsyncIterMock(["session:GUEST:1", "session:GUEST:2", "session:GUEST:3"])
        )

        with patch(f"{_AUTH_SVC}.get_redis", return_value=mock_redis):
            from app.services.auth import _get_guest_count

            count = await _get_guest_count()

        assert count == 3
        # set called with count=3 and nx=True
        mock_redis.set.assert_called_once()
        args, kwargs = mock_redis.set.call_args
        assert args[1] == 3
        assert kwargs.get("nx") is True


class AsyncIterMock:
    """Helper to mock async iterators like redis.scan_iter."""

    def __init__(self, items):
        self._items = list(items)

    def __aiter__(self):
        self._iter = iter(self._items)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


# ── F-42: asyncpg.execute() string comparison ────────────────────────────


class TestF42AsyncpgResultParsing:
    """Admin endpoints use .endswith(' 0') instead of == 'UPDATE 0'."""

    @pytest.mark.anyio
    async def test_revoke_invite_code_update_zero(self, client):
        """Revoke endpoint handles UPDATE 0 result robustly."""
        code_id = uuid.uuid4()
        try:
            payload, uid = _override_auth("ADMIN")

            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock(return_value="UPDATE 0")
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(return_value=mock_conn)
            cm.__aexit__ = AsyncMock(return_value=False)
            mock_pool.acquire = MagicMock(return_value=cm)

            with (
                patch("app.core.database.get_pool", return_value=mock_pool),
                patch(f"{_ADMIN_EP}.invite_code_repo") as mock_repo,
            ):
                mock_repo.find_by_id = AsyncMock(return_value=None)
                resp = await client.patch(f"/api/v1/admin/invite-codes/{code_id}/revoke")
            assert resp.status_code == 404
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_revoke_invite_code_update_one_succeeds(self, client):
        """Revoke endpoint succeeds when UPDATE returns 1 row."""
        code_id = uuid.uuid4()
        try:
            payload, uid = _override_auth("ADMIN")

            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock(return_value="UPDATE 1")
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(return_value=mock_conn)
            cm.__aexit__ = AsyncMock(return_value=False)
            mock_pool.acquire = MagicMock(return_value=cm)

            with (
                patch("app.core.database.get_pool", return_value=mock_pool),
                patch("app.core.event_bus.emit", new_callable=AsyncMock),
            ):
                resp = await client.patch(f"/api/v1/admin/invite-codes/{code_id}/revoke")
            assert resp.status_code == 200
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_delete_invite_code_delete_zero(self, client):
        """Delete endpoint handles DELETE 0 result robustly."""
        code_id = uuid.uuid4()
        try:
            payload, uid = _override_auth("ADMIN")

            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock(return_value="DELETE 0")
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(return_value=mock_conn)
            cm.__aexit__ = AsyncMock(return_value=False)
            mock_pool.acquire = MagicMock(return_value=cm)

            with (
                patch("app.core.database.get_pool", return_value=mock_pool),
                patch(f"{_ADMIN_EP}.invite_code_repo") as mock_repo,
            ):
                mock_repo.find_by_id = AsyncMock(return_value=None)
                resp = await client.delete(f"/api/v1/admin/invite-codes/{code_id}")
            assert resp.status_code == 404
        finally:
            _clear_overrides()


# ── F-43: Form response permission defense-in-depth ─────────────────────


class TestF43FormResponseGuestGuard:
    """insert_response raises PermissionError when guest_allowed=False and user_id=None."""

    @pytest.mark.anyio
    async def test_guest_not_allowed_raises_permission_error(self):
        """Repository rejects guest submission when guest_allowed=False."""
        from app.repositories.form_repo import insert_response

        mock_conn = AsyncMock()
        with pytest.raises(PermissionError, match="does not allow guest"):
            await insert_response(
                response_id=uuid.uuid4(),
                form_id=uuid.uuid4(),
                user_id=None,
                answers={"q1": "test"},
                conn=mock_conn,
                guest_allowed=False,
            )

    @pytest.mark.anyio
    async def test_guest_allowed_proceeds(self):
        """Repository allows guest submission when guest_allowed=True."""
        from app.repositories.form_repo import insert_response

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="INSERT 0 1")

        result = await insert_response(
            response_id=uuid.uuid4(),
            form_id=uuid.uuid4(),
            user_id=None,
            answers={"q1": "test"},
            conn=mock_conn,
            guest_allowed=True,
        )
        assert result is True

    @pytest.mark.anyio
    async def test_authenticated_user_bypasses_guest_check(self):
        """Repository does not check guest_allowed for authenticated users."""
        from app.repositories.form_repo import insert_response

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="INSERT 0 1")

        result = await insert_response(
            response_id=uuid.uuid4(),
            form_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            answers={"q1": "test"},
            conn=mock_conn,
            guest_allowed=False,
        )
        assert result is True


# ── F-44: get_dm_friends_only returns None for non-existent users ────────


class TestF44DmFriendsOnlyNonExistent:
    """get_dm_friends_only distinguishes between 'no preference' and 'no user'."""

    @pytest.mark.anyio
    async def test_returns_none_for_deleted_user(self):
        """User with is_deleted=TRUE returns None."""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        # User does not exist (is_deleted=TRUE or missing)
        mock_conn.fetchval = AsyncMock(return_value=None)
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire = MagicMock(return_value=cm)

        with patch(f"{_DM_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import get_dm_friends_only

            result = await get_dm_friends_only(uuid.uuid4())

        assert result is None

    @pytest.mark.anyio
    async def test_returns_false_for_existing_user_no_prefs(self):
        """Existing user with no preference row returns False."""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        # First call: user exists (returns 1), second call: no preference row
        mock_conn.fetchval = AsyncMock(side_effect=[1, None])
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire = MagicMock(return_value=cm)

        with patch(f"{_DM_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import get_dm_friends_only

            result = await get_dm_friends_only(uuid.uuid4())

        assert result is False

    @pytest.mark.anyio
    async def test_returns_true_for_existing_user_with_pref(self):
        """Existing user with dm_friends_only=True returns True."""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=[1, True])
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire = MagicMock(return_value=cm)

        with patch(f"{_DM_REPO}.get_pool", return_value=mock_pool):
            from app.repositories.dm_repo import get_dm_friends_only

            result = await get_dm_friends_only(uuid.uuid4())

        assert result is True


# ── F-45: update_my_profile validates non-clearable fields ───────────────


class TestF45NonClearableFields:
    """display_name cannot be set to None or empty string."""

    @pytest.mark.anyio
    async def test_display_name_none_raises(self):
        """Setting display_name to None raises ValueError."""
        from app.services.user import update_user_profile

        with pytest.raises(ValueError, match="display_name cannot be empty"):
            await update_user_profile(uuid.uuid4(), display_name=None)

    @pytest.mark.anyio
    async def test_display_name_empty_raises(self):
        """Setting display_name to empty string raises ValueError."""
        from app.services.user import update_user_profile

        with pytest.raises(ValueError, match="display_name cannot be empty"):
            await update_user_profile(uuid.uuid4(), display_name="")

    @pytest.mark.anyio
    async def test_display_name_whitespace_raises(self):
        """Setting display_name to whitespace-only raises ValueError."""
        from app.services.user import update_user_profile

        with pytest.raises(ValueError, match="display_name cannot be empty"):
            await update_user_profile(uuid.uuid4(), display_name="   ")

    @pytest.mark.anyio
    async def test_bio_can_be_cleared(self):
        """Setting bio to None is allowed (clearable field)."""
        from app.services.user import update_user_profile

        with patch("app.services.user.user_repo") as mock_repo:
            mock_repo.update_profile = AsyncMock(return_value={"id": uuid.uuid4()})
            result = await update_user_profile(uuid.uuid4(), bio=None)
            assert result is not None

    @pytest.mark.anyio
    async def test_valid_display_name_passes(self):
        """Setting display_name to valid value succeeds."""
        from app.services.user import update_user_profile

        with patch("app.services.user.user_repo") as mock_repo:
            mock_repo.update_profile = AsyncMock(return_value={"id": uuid.uuid4()})
            result = await update_user_profile(uuid.uuid4(), display_name="New Name")
            assert result is not None


# ── F-57: Missing explicit sub None check ────────────────────────────────


class TestF57SubNoneCheck:
    """co-author invitations endpoint checks for None sub."""

    @pytest.mark.anyio
    async def test_missing_sub_returns_401(self, client):
        """Endpoint returns 401 when sub is missing from current_user."""
        from app.core.deps import get_current_user
        from app.main import app

        try:
            # Override with a payload that has no sub
            payload = {"sub": None, "role": "MEMBER", "jti": str(uuid.uuid4())}
            app.dependency_overrides[get_current_user] = lambda: payload

            resp = await client.get("/api/v1/users/me/co-author-invitations")
            assert resp.status_code == 401
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_valid_sub_succeeds(self, client):
        """Endpoint succeeds when sub is present."""
        try:
            payload, uid = _override_auth("MEMBER")
            with patch(
                "app.services.co_author.list_pending_invitations",
                new_callable=AsyncMock,
                return_value=([], 0),
            ):
                resp = await client.get("/api/v1/users/me/co-author-invitations")
            assert resp.status_code == 200
        finally:
            _clear_overrides()


# ── F-58: Form responses auth timing oracle ──────────────────────────────


class TestF58FormResponsesTimingOracle:
    """Unauthorized users get 404 (not 403) for form responses."""

    @pytest.mark.anyio
    async def test_unauthorized_returns_404_not_403(self, client):
        """Non-admin, non-creator gets 404 to prevent form existence leak."""
        form_id = uuid.uuid4()
        creator_id = str(uuid.uuid4())
        try:
            payload, uid = _override_auth("MEMBER")
            form = {
                "id": form_id,
                "title": "Test",
                "sig_id": None,
                "created_by": creator_id,  # Different from current user
            }
            with (
                patch(
                    f"{_FORMS_EP}.get_form_by_id",
                    new_callable=AsyncMock,
                    return_value=form,
                ),
                patch(
                    f"{_FORMS_EP}.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
            ):
                resp = await client.get(f"/api/v1/forms/forms/{form_id}/responses")
            assert resp.status_code == 404
            # Should NOT say "Only admins" — should say "Form not found"
            data = resp.json()
            assert "not found" in data.get("detail", "").lower()
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_missing_form_returns_404(self, client):
        """Non-existent form returns 404."""
        form_id = uuid.uuid4()
        try:
            payload, uid = _override_auth("MEMBER")
            with (
                patch(
                    f"{_FORMS_EP}.get_form_by_id",
                    new_callable=AsyncMock,
                    return_value=None,
                ),
                patch(
                    f"{_FORMS_EP}.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
            ):
                resp = await client.get(f"/api/v1/forms/forms/{form_id}/responses")
            assert resp.status_code == 404
        finally:
            _clear_overrides()
