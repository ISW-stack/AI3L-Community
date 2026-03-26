"""Tests for functional bug fixes F-01, F-02, F-05.

F-01: Guest form submission FK violation (user_id=None for guests)
F-02: DM edit/recall returning empty sender info (_enrich_with_sender)
F-05: Heartbeat JWT refresh (refresh_access_token + endpoint cookie)
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.errors import AppError, ErrorCode

# ── Module path aliases ─────────────────────────────────────────────────────

_FORM_SVC = "app.services.form"
_DM_SVC = "app.services.dm"
_AUTH_EP = "app.api.v1.endpoints.auth"

_NOW = datetime.now(timezone.utc)
_USER_ID = str(uuid.uuid4())
_FORM_ID = uuid.uuid4()


# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_form_row(
    form_id=None,
    allow_non_members=False,
    is_closed=False,
    deadline=None,
    max_respondents=None,
    is_schema_locked=True,
    sig_id=None,
    created_by=None,
):
    return {
        "id": form_id or _FORM_ID,
        "title": "Test Form",
        "description": "desc",
        "questions": '[{"id": "q1", "type": "text", "label": "Name", "required": false}]',
        "allow_non_members": allow_non_members,
        "is_closed": is_closed,
        "deadline": deadline,
        "max_respondents": max_respondents,
        "is_schema_locked": is_schema_locked,
        "sig_id": sig_id,
        "created_by": created_by or uuid.uuid4(),
        "created_at": _NOW,
        "updated_at": _NOW,
    }


def _mock_pool_with_conn(mock_conn):
    """Create a mock pool whose acquire() yields the given mock_conn."""
    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = cm
    return pool


def _mock_conn():
    """Create a mock asyncpg connection with transaction support."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    conn.execute = AsyncMock(return_value="UPDATE 1")

    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)

    return conn


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


# ═════════════════════════════════════════════════════════════════════════════
# F-01: Guest form submission FK violation
# ═════════════════════════════════════════════════════════════════════════════


class TestF01GuestFormSubmission:
    """Guest submissions must pass user_id=None to insert_response to avoid FK violation."""

    @patch(f"{_FORM_SVC}.form_repo")
    @patch(f"{_FORM_SVC}.get_pool")
    @patch(f"{_FORM_SVC}.get_redis")
    @patch(f"{_FORM_SVC}.get_blocked_user_ids", new_callable=AsyncMock, return_value=set())
    async def test_guest_passes_none_user_id(
        self, mock_blocked, mock_get_redis, mock_get_pool, mock_form_repo
    ):
        """Guest submissions should pass None as user_id to insert_response (no FK)."""
        from app.services.form import submit_response

        conn = _mock_conn()
        pool = _mock_pool_with_conn(conn)
        mock_get_pool.return_value = pool

        form_row = _make_form_row(allow_non_members=True)
        mock_form_repo.find_for_update = AsyncMock(return_value=form_row)
        mock_form_repo.insert_response = AsyncMock(return_value=True)
        mock_form_repo.lock_schema = AsyncMock()

        guest_id = str(uuid.uuid4())
        answers = {"q1": "Alice"}

        result = await submit_response(_FORM_ID, guest_id, answers, is_guest=True)

        assert result["message"] == "Response submitted successfully."

        # The critical assertion: user_id arg (index 2) must be None, not a UUID
        call_args = mock_form_repo.insert_response.call_args
        actual_user_id = call_args[0][2]  # positional arg index 2 = db_user_id
        assert actual_user_id is None, f"Expected None for guest user_id, got {actual_user_id}"

    @patch(f"{_FORM_SVC}.form_repo")
    @patch(f"{_FORM_SVC}.get_pool")
    @patch(f"{_FORM_SVC}.get_redis")
    @patch(f"{_FORM_SVC}.get_blocked_user_ids", new_callable=AsyncMock, return_value=set())
    async def test_guest_rejected_when_form_disallows_non_members(
        self, mock_blocked, mock_get_redis, mock_get_pool, mock_form_repo
    ):
        """Guests cannot submit forms where allow_non_members=False."""
        from app.services.form import submit_response

        conn = _mock_conn()
        pool = _mock_pool_with_conn(conn)
        mock_get_pool.return_value = pool

        form_row = _make_form_row(allow_non_members=False)
        mock_form_repo.find_for_update = AsyncMock(return_value=form_row)

        guest_id = str(uuid.uuid4())
        answers = {"q1": "Alice"}

        with pytest.raises(PermissionError, match="Guests cannot submit this form"):
            await submit_response(_FORM_ID, guest_id, answers, is_guest=True)

    @patch(f"{_FORM_SVC}.form_repo")
    @patch(f"{_FORM_SVC}.get_pool")
    @patch(f"{_FORM_SVC}.get_redis")
    @patch(f"{_FORM_SVC}.get_blocked_user_ids", new_callable=AsyncMock, return_value=set())
    async def test_guest_skips_duplicate_check(
        self, mock_blocked, mock_get_redis, mock_get_pool, mock_form_repo
    ):
        """Duplicate response check should be skipped for guest submissions."""
        from app.services.form import submit_response

        conn = _mock_conn()
        pool = _mock_pool_with_conn(conn)
        mock_get_pool.return_value = pool

        form_row = _make_form_row(allow_non_members=True)
        mock_form_repo.find_for_update = AsyncMock(return_value=form_row)
        mock_form_repo.check_duplicate_response = AsyncMock(return_value=True)
        mock_form_repo.insert_response = AsyncMock(return_value=True)
        mock_form_repo.lock_schema = AsyncMock()

        guest_id = str(uuid.uuid4())
        answers = {"q1": "Alice"}

        # Should succeed even though check_duplicate_response would return True
        result = await submit_response(_FORM_ID, guest_id, answers, is_guest=True)
        assert result["message"] == "Response submitted successfully."

        # check_duplicate_response should never be called for guests
        mock_form_repo.check_duplicate_response.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# F-02: DM edit/recall returning empty sender info
# ═════════════════════════════════════════════════════════════════════════════


class TestF02EnrichWithSender:
    """_enrich_with_sender should fill missing sender info via DB lookup."""

    @patch("app.core.database.get_pool")
    async def test_enriches_row_missing_sender_display_name(self, mock_get_pool):
        """Row without sender_display_name gets enriched from users table."""
        from app.services.dm import _enrich_with_sender

        sender_id = uuid.uuid4()
        conn = _mock_conn()
        conn.fetchrow = AsyncMock(
            return_value={"display_name": "Jane Doe", "avatar_url": "avatars/jane.png"}
        )
        pool = _mock_pool_with_conn(conn)
        mock_get_pool.return_value = pool

        row = {
            "id": uuid.uuid4(),
            "sender_id": sender_id,
            "sender_display_name": None,
            "sender_avatar_url": None,
            "content": "Hello",
        }

        enriched = await _enrich_with_sender(row)

        assert enriched["sender_display_name"] == "Jane Doe"
        assert enriched["sender_avatar_url"] == "avatars/jane.png"
        conn.fetchrow.assert_called_once()

    @patch("app.core.database.get_pool")
    async def test_returns_row_as_is_when_already_enriched(self, mock_get_pool):
        """Row with existing sender_display_name should be returned without DB call."""
        from app.services.dm import _enrich_with_sender

        row = {
            "id": uuid.uuid4(),
            "sender_id": uuid.uuid4(),
            "sender_display_name": "Already Here",
            "sender_avatar_url": "avatars/existing.png",
            "content": "Hello",
        }

        enriched = await _enrich_with_sender(row)

        assert enriched["sender_display_name"] == "Already Here"
        assert enriched["sender_avatar_url"] == "avatars/existing.png"
        # Pool should never be accessed
        mock_get_pool.assert_not_called()

    @patch("app.core.database.get_pool")
    async def test_no_crash_when_user_row_is_none(self, mock_get_pool):
        """When user lookup returns None, row is returned without enrichment (no crash)."""
        from app.services.dm import _enrich_with_sender

        sender_id = uuid.uuid4()
        conn = _mock_conn()
        conn.fetchrow = AsyncMock(return_value=None)
        pool = _mock_pool_with_conn(conn)
        mock_get_pool.return_value = pool

        row = {
            "id": uuid.uuid4(),
            "sender_id": sender_id,
            "sender_display_name": None,
            "sender_avatar_url": None,
            "content": "Hello",
        }

        enriched = await _enrich_with_sender(row)

        # Should not crash — sender fields remain absent or None
        assert "sender_display_name" not in enriched or enriched.get("sender_display_name") is None
        conn.fetchrow.assert_called_once()


# ═════════════════════════════════════════════════════════════════════════════
# F-05: Heartbeat JWT refresh
# ═════════════════════════════════════════════════════════════════════════════


class TestF05RefreshAccessToken:
    """refresh_access_token should return JWT with same JTI and correct TTL."""

    async def test_returns_valid_jwt_with_same_jti(self):
        """Refreshed token should contain the same JTI but a new exp."""
        from app.core.security import decode_access_token, refresh_access_token

        user_id = str(uuid.uuid4())
        jti = str(uuid.uuid4())
        role = "MEMBER"

        token, ttl = refresh_access_token(user_id, role, jti, timedelta(hours=1))

        # Decode and verify
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["role"] == role
        assert payload["jti"] == jti

    async def test_returns_correct_ttl_seconds(self):
        """ttl_seconds should match the requested expires_delta."""
        from app.core.security import refresh_access_token

        user_id = str(uuid.uuid4())
        jti = str(uuid.uuid4())
        delta = timedelta(hours=2)

        token, ttl = refresh_access_token(user_id, "MEMBER", jti, delta)

        assert ttl == int(delta.total_seconds())
        assert ttl == 7200


class TestF05HeartbeatEndpointCookie:
    """Heartbeat endpoint should set new access_token cookie after JWT refresh."""

    @patch(f"{_AUTH_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True)
    @patch(f"{_AUTH_EP}.refresh_session_ttl", new_callable=AsyncMock, return_value=True)
    async def test_heartbeat_sets_access_token_cookie(
        self, mock_refresh, mock_rl, client: AsyncClient
    ):
        """POST /auth/heartbeat should return 200 and set a new access_token cookie."""
        from app.core.deps import get_current_user
        from app.main import app

        user_id = str(uuid.uuid4())
        jti = str(uuid.uuid4())
        payload = {"sub": user_id, "role": "MEMBER", "jti": jti}
        app.dependency_overrides[get_current_user] = lambda: payload
        try:
            resp = await client.post(
                "/api/v1/auth/heartbeat", headers={"Authorization": "Bearer fake"}
            )
            assert resp.status_code == 200
            assert resp.json()["message"] == "Session refreshed."

            # Verify access_token cookie is set in response
            set_cookie_headers = resp.headers.get_list("set-cookie")
            cookie_names = [h.split("=")[0].strip() for h in set_cookie_headers]
            assert "access_token" in cookie_names, (
                f"Expected access_token cookie in response, got: {cookie_names}"
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
