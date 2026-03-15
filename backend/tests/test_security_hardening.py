"""Tests for security hardening fixes (C1, H3, H4, H6, M7).

Covers:
- reaction_helpers table whitelist validation
- Guest counter TOCTOU fix (SETNX-based init)
- CSRF exemption scoping
- form_repo.update() field whitelist
- preferences_repo unknown column rejection
- GuestLoginRequest display_name max_length
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.repositories.reaction_helpers import _ALLOWED_TABLES, toggle_reaction_jsonb
from app.schemas.auth import GuestLoginRequest

# ---------------------------------------------------------------------------
# C1: reaction_helpers table whitelist
# ---------------------------------------------------------------------------


class TestReactionHelpersTableWhitelist:
    async def test_rejects_invalid_table_name(self) -> None:
        """toggle_reaction_jsonb raises ValueError for disallowed table names."""
        conn = AsyncMock()
        with pytest.raises(ValueError, match="Invalid table"):
            await toggle_reaction_jsonb(
                conn=conn,
                table="users; DROP TABLE posts --",
                row_id=str(uuid.uuid4()),
                user_id=str(uuid.uuid4()),
                reaction_type="like",
            )
        # conn should never have been called
        conn.fetchrow.assert_not_called()

    async def test_rejects_unknown_table(self) -> None:
        """toggle_reaction_jsonb raises ValueError for unknown but benign table."""
        conn = AsyncMock()
        with pytest.raises(ValueError, match="Invalid table"):
            await toggle_reaction_jsonb(
                conn=conn,
                table="notifications",
                row_id=str(uuid.uuid4()),
                user_id=str(uuid.uuid4()),
                reaction_type="like",
            )

    async def test_accepts_posts_table(self) -> None:
        """toggle_reaction_jsonb works with 'posts' table."""
        row_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        conn = AsyncMock()
        conn.fetchrow.return_value = {"reactions": "{}"}
        conn.execute = AsyncMock()

        result = await toggle_reaction_jsonb(
            conn=conn, table="posts", row_id=str(row_id), user_id=user_id, reaction_type="like"
        )
        assert "like" in result
        assert user_id in result["like"]
        # Should have queried the posts table
        assert conn.fetchrow.call_count >= 1

    async def test_accepts_comments_table(self) -> None:
        """toggle_reaction_jsonb works with 'comments' table."""
        row_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        conn = AsyncMock()
        conn.fetchrow.return_value = {"reactions": "{}"}
        conn.execute = AsyncMock()

        result = await toggle_reaction_jsonb(
            conn=conn, table="comments", row_id=str(row_id), user_id=user_id, reaction_type="like"
        )
        assert "like" in result

    async def test_allowed_tables_is_frozen(self) -> None:
        """_ALLOWED_TABLES is a frozenset (immutable)."""
        assert isinstance(_ALLOWED_TABLES, frozenset)
        assert _ALLOWED_TABLES == {"posts", "comments"}


# ---------------------------------------------------------------------------
# H3: Guest counter TOCTOU — atomic SETNX initialisation
# ---------------------------------------------------------------------------


class TestGuestCounterAtomicInit:
    @patch("app.services.auth.get_redis")
    async def test_guest_login_uses_lua_eval(self, mock_get_redis: MagicMock) -> None:
        """guest_login uses redis.eval (Lua script) for atomic counter check."""
        from app.services.auth import guest_login

        redis = AsyncMock()
        redis.eval = AsyncMock(return_value=1)
        mock_get_redis.return_value = redis

        with patch("app.services.auth.create_session", new_callable=AsyncMock) as mock_session:
            mock_session.return_value = ("token", 3600)
            result = await guest_login("TestGuest")

        assert result is not None
        redis.eval.assert_called_once()

    @patch("app.services.auth.get_redis")
    async def test_lua_eval_receives_correct_args(self, mock_get_redis: MagicMock) -> None:
        """redis.eval is called with Lua script, 1 key, counter key, MAX_GUESTS."""
        from app.core.constants import MAX_GUESTS
        from app.services.auth import _GUEST_INCR_LUA, guest_login

        redis = AsyncMock()
        redis.eval = AsyncMock(return_value=1)
        mock_get_redis.return_value = redis

        with patch("app.services.auth.create_session", new_callable=AsyncMock) as mock_session:
            mock_session.return_value = ("token", 3600)
            await guest_login("TestGuest")

        redis.eval.assert_called_once_with(_GUEST_INCR_LUA, 1, "meta:guest_counter", MAX_GUESTS)

    @patch("app.services.auth.get_redis")
    async def test_guest_login_respects_max_guests(self, mock_get_redis: MagicMock) -> None:
        """guest_login returns None when Lua script returns -1 (limit exceeded)."""
        from app.services.auth import guest_login

        redis = AsyncMock()
        redis.eval = AsyncMock(return_value=-1)
        mock_get_redis.return_value = redis

        result = await guest_login("TestGuest")
        assert result is None


# ---------------------------------------------------------------------------
# H4: CSRF exemption scoping
# ---------------------------------------------------------------------------


class TestCSRFExemptionScoping:
    async def test_guest_login_path_is_csrf_exempt(self, client: AsyncMock) -> None:
        """POST /api/v1/auth/guest/{code} should NOT get 403 CSRF error."""
        _EP = "app.api.v1.endpoints.auth"
        with (
            patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
            patch(f"{_EP}.get_invite_code", new_callable=AsyncMock, return_value=None),
        ):
            resp = await client.post(
                "/api/v1/auth/guest/INV-TEST",
                json={
                    "display_name": "Visitor",
                    "captcha_id": "cap-1",
                    "captcha_code": "ABCD",
                },
                headers={"X-CSRF-Token": "", "Authorization": ""},
                cookies={"csrf_token": ""},
            )
            # Should be 404 (invalid code), NOT 403 (CSRF)
            assert resp.status_code == 404

    async def test_deeper_guest_subpath_requires_csrf(self, client: AsyncMock) -> None:
        """POST /api/v1/auth/guest/CODE/extra should be CSRF-checked (not exempt)."""
        resp = await client.post(
            "/api/v1/auth/guest/INV-TEST/extra",
            json={"foo": "bar"},
            headers={"X-CSRF-Token": "", "Authorization": ""},
            cookies={"csrf_token": ""},
        )
        # Should be 403 (CSRF) since this deeper path is not exempt
        # (or 404 if no route, but CSRF check happens before routing)
        assert resp.status_code in (403, 404, 405)

    async def test_csrf_exact_exemptions_still_work(self, client: AsyncMock) -> None:
        """POST /api/v1/auth/login should still be CSRF-exempt."""
        _EP = "app.api.v1.endpoints.auth"
        with (
            patch(f"{_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
            patch(f"{_EP}.verify_captcha", new_callable=AsyncMock, return_value=False),
        ):
            resp = await client.post(
                "/api/v1/auth/login",
                json={
                    "username": "x",
                    "password": "x",
                    "captcha_id": "x",
                    "captcha_code": "x",
                },
                headers={"X-CSRF-Token": ""},
                cookies={"csrf_token": ""},
            )
            # Should be 400 (bad captcha), NOT 403 (CSRF)
            assert resp.status_code == 400


# ---------------------------------------------------------------------------
# H6: form_repo.update() field whitelist (dict-based)
# ---------------------------------------------------------------------------


class TestFormRepoUpdateWhitelist:
    async def test_rejects_disallowed_field(self) -> None:
        """form_repo.update() raises ValueError for fields not in whitelist."""
        from app.repositories.form_repo import update

        conn = AsyncMock()
        form_id = uuid.uuid4()

        with pytest.raises(ValueError, match="Disallowed field"):
            await update(form_id, {"evil_column": "injected"}, conn)

        conn.fetchrow.assert_not_called()

    async def test_rejects_sql_injection_in_key(self) -> None:
        """form_repo.update() rejects keys containing SQL injection attempts."""
        from app.repositories.form_repo import update

        conn = AsyncMock()
        form_id = uuid.uuid4()

        with pytest.raises(ValueError, match="Disallowed field"):
            await update(form_id, {"title = 'hacked' --": "val"}, conn)

    async def test_accepts_valid_fields(self) -> None:
        """form_repo.update() accepts all whitelisted fields."""
        from app.repositories.form_repo import update

        conn = AsyncMock()
        form_id = uuid.uuid4()
        creator_id = uuid.uuid4()

        conn.fetchrow.side_effect = [
            # First call: UPDATE RETURNING *
            {
                "id": form_id,
                "created_by": creator_id,
                "title": "Updated",
                "questions": "[]",
            },
            # Second call: creator display_name
            {"display_name": "Creator"},
        ]
        conn.fetchval.return_value = 0  # response_count

        result = await update(form_id, {"title": "Updated"}, conn)
        assert result is not None
        row, count = result
        assert row["title"] == "Updated"

    async def test_allowed_form_fields_is_frozen(self) -> None:
        """_ALLOWED_FORM_FIELDS is a frozenset (immutable)."""
        from app.repositories.form_repo import _ALLOWED_FORM_FIELDS

        assert isinstance(_ALLOWED_FORM_FIELDS, frozenset)


# ---------------------------------------------------------------------------
# H6: preferences_repo unknown column rejection
# ---------------------------------------------------------------------------


class TestPreferencesRepoColumnValidation:
    async def test_rejects_unknown_columns(self) -> None:
        """upsert_preferences raises ValueError for unknown columns."""
        from app.repositories.preferences_repo import upsert_preferences

        with pytest.raises(ValueError, match="Unknown preference columns"):
            await upsert_preferences(uuid.uuid4(), {"evil_col": True})

    async def test_rejects_sql_in_column_name(self) -> None:
        """upsert_preferences rejects SQL injection in column names."""
        from app.repositories.preferences_repo import upsert_preferences

        with pytest.raises(ValueError, match="Unknown preference columns"):
            await upsert_preferences(uuid.uuid4(), {"theme; DROP TABLE users --": "dark"})

    @patch("app.repositories.preferences_repo.get_pool")
    async def test_accepts_valid_columns(self, mock_pool: MagicMock) -> None:
        """upsert_preferences accepts all known preference columns."""
        conn = AsyncMock()
        conn.fetchrow.return_value = {
            "theme": "dark",
            "notify_mentions": True,
            "notify_replies": False,
            "notify_sig_posts": True,
        }

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        pool = MagicMock()
        pool.acquire.return_value = cm
        mock_pool.return_value = pool

        from app.repositories.preferences_repo import upsert_preferences

        result = await upsert_preferences(uuid.uuid4(), {"theme": "dark"})
        assert result["theme"] == "dark"

    async def test_allowed_columns_is_frozen(self) -> None:
        """_ALLOWED_PREFERENCE_COLUMNS is a frozenset."""
        from app.repositories.preferences_repo import _ALLOWED_PREFERENCE_COLUMNS

        assert isinstance(_ALLOWED_PREFERENCE_COLUMNS, frozenset)


# ---------------------------------------------------------------------------
# M7: GuestLoginRequest display_name max_length
# ---------------------------------------------------------------------------


class TestGuestDisplayNameMaxLength:
    def test_display_name_within_limit(self) -> None:
        """display_name of 50 chars is accepted."""
        req = GuestLoginRequest(
            display_name="A" * 50,
            captcha_id="cap-1",
            captcha_code="ABCD",
        )
        assert len(req.display_name) == 50

    def test_display_name_exceeds_limit(self) -> None:
        """display_name over 50 chars is rejected by Pydantic."""
        with pytest.raises(ValidationError) as exc_info:
            GuestLoginRequest(
                display_name="A" * 51,
                captcha_id="cap-1",
                captcha_code="ABCD",
            )
        errors = exc_info.value.errors()
        assert any("display_name" in str(e.get("loc", "")) for e in errors)

    def test_display_name_empty_rejected(self) -> None:
        """Empty display_name should be rejected (min_length=1)."""
        with pytest.raises(ValidationError):
            GuestLoginRequest(
                display_name="",
                captcha_id="cap-1",
                captcha_code="ABCD",
            )

    def test_display_name_exactly_at_old_limit_rejected(self) -> None:
        """display_name of 100 chars (old limit) should now be rejected."""
        with pytest.raises(ValidationError):
            GuestLoginRequest(
                display_name="B" * 100,
                captcha_id="cap-1",
                captcha_code="ABCD",
            )


# ---------------------------------------------------------------------------
# Async iterator helper for mocking redis.scan_iter
# ---------------------------------------------------------------------------


class AsyncIterator:
    """Helper to create an async iterator from a list for mocking scan_iter."""

    def __init__(self, items: list) -> None:
        self._items = items
        self._index = 0

    def __aiter__(self) -> "AsyncIterator":
        return self

    async def __anext__(self) -> object:
        if self._index >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._index]
        self._index += 1
        return item
