"""Tests for audit findings M-18, M-19, M-31, M-34, M-35, L-44, M-47, L-47.

Covers:
  M-18  album_repo regex guard on dynamic column names
  M-19  preferences_repo regex guard on column names
  M-31  FormSubmitRequest.answers validation
  M-34  SIG endpoint offset bounds
  M-35  Admin user search max_length
  L-44  Cursor parsing returns generic error
  M-47  Password change error message sanitization
  L-47  about.py avatar content-length parsing
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

_SIG_EP = "app.api.v1.endpoints.sigs"
_USERS_EP = "app.api.v1.endpoints.users"
_POSTS_EP = "app.api.v1.endpoints.posts"

# ---------------------------------------------------------------------------
# M-18: album_repo regex guard
# ---------------------------------------------------------------------------


class TestAlbumRepoRegexGuard:
    """M-18: update_album / update_photo skip columns that fail regex."""

    @pytest.mark.anyio
    async def test_update_album_rejects_bad_column_name(self, mock_conn):
        from app.repositories.album_repo import update_album

        mock_conn.fetchrow = AsyncMock(return_value=None)
        result = await update_album(mock_conn, uuid.uuid4(), **{"title; DROP TABLE--": "x"})
        assert result is None

    @pytest.mark.anyio
    async def test_update_album_accepts_valid_column(self, mock_conn):
        from app.repositories.album_repo import update_album

        fake_album_id = uuid.uuid4()
        mock_conn.fetchrow = AsyncMock(side_effect=[{"id": fake_album_id, "title": "new"}, None])
        await update_album(mock_conn, fake_album_id, title="new")
        call_args = mock_conn.fetchrow.call_args_list[0]
        query = call_args[0][0]
        assert "title = $1" in query

    @pytest.mark.anyio
    async def test_update_album_skips_uppercase_column(self, mock_conn):
        from app.repositories.album_repo import update_album

        mock_conn.fetchrow = AsyncMock(return_value=None)
        result = await update_album(mock_conn, uuid.uuid4(), **{"TITLE": "x"})
        assert result is None

    @pytest.mark.anyio
    async def test_update_photo_rejects_bad_column_name(self, mock_conn):
        from app.repositories.album_repo import update_photo

        mock_conn.fetchrow = AsyncMock(return_value=None)
        result = await update_photo(mock_conn, uuid.uuid4(), **{"desc; DROP--": "x"})
        assert result is None

    @pytest.mark.anyio
    async def test_update_photo_accepts_valid_column(self, mock_conn):
        from app.repositories.album_repo import update_photo

        fake_id = uuid.uuid4()
        mock_conn.fetchrow = AsyncMock(
            return_value={"id": fake_id, "description": "updated", "uploaded_by_name": "test"}
        )
        await update_photo(mock_conn, fake_id, description="updated")
        call_args = mock_conn.fetchrow.call_args_list[0]
        query = call_args[0][0]
        assert "description = $1" in query


# ---------------------------------------------------------------------------
# M-19: preferences_repo regex guard
# ---------------------------------------------------------------------------


class TestPreferencesRepoRegexGuard:
    """M-19: upsert_preferences rejects columns failing regex."""

    @pytest.mark.anyio
    async def test_upsert_rejects_unknown_column(self):
        from app.repositories.preferences_repo import upsert_preferences

        with pytest.raises(ValueError, match="Unknown preference columns"):
            await upsert_preferences(uuid.uuid4(), {"evil_col": True})

    @pytest.mark.anyio
    async def test_upsert_skips_column_with_special_chars(self, mock_pool):
        """Even if somehow in the allowed set, columns with bad chars are filtered."""
        from app.repositories import preferences_repo

        original = preferences_repo._ALLOWED_PREFERENCE_COLUMNS
        try:
            preferences_repo._ALLOWED_PREFERENCE_COLUMNS = frozenset(original | {"bad;col"})
            with patch.object(preferences_repo, "get_pool", return_value=mock_pool):
                result = await preferences_repo.upsert_preferences(uuid.uuid4(), {"bad;col": True})
                assert "theme" in result
        finally:
            preferences_repo._ALLOWED_PREFERENCE_COLUMNS = original

    @pytest.mark.anyio
    async def test_upsert_accepts_valid_column(self, mock_pool, mock_conn):
        from app.repositories import preferences_repo

        mock_conn.fetchrow = AsyncMock(
            return_value={
                "theme": "dark",
                "notify_mentions": True,
                "notify_replies": True,
                "notify_sig_posts": True,
                "dm_friends_only": False,
            }
        )
        with patch.object(preferences_repo, "get_pool", return_value=mock_pool):
            result = await preferences_repo.upsert_preferences(uuid.uuid4(), {"theme": "dark"})
            assert result["theme"] == "dark"


# ---------------------------------------------------------------------------
# M-31: FormSubmitRequest.answers validation
# ---------------------------------------------------------------------------


class TestFormSubmitRequestValidation:
    """M-31: answers dict must pass type/size constraints."""

    def test_valid_answers(self):
        from app.schemas.form import FormSubmitRequest

        req = FormSubmitRequest(
            answers={"q1": "hello", "q2": 42, "q3": True, "q4": ["a", "b"], "q5": None}
        )
        assert len(req.answers) == 5

    def test_too_many_keys(self):
        from app.schemas.form import FormSubmitRequest

        answers = {f"q{i}": "val" for i in range(201)}
        with pytest.raises(ValidationError, match="Too many answers"):
            FormSubmitRequest(answers=answers)

    def test_empty_key(self):
        from app.schemas.form import FormSubmitRequest

        with pytest.raises(ValidationError, match="Answer key must be 1-100 characters"):
            FormSubmitRequest(answers={"": "val"})

    def test_key_too_long(self):
        from app.schemas.form import FormSubmitRequest

        with pytest.raises(ValidationError, match="Answer key must be 1-100 characters"):
            FormSubmitRequest(answers={"x" * 101: "val"})

    def test_value_too_long_string(self):
        from app.schemas.form import FormSubmitRequest

        with pytest.raises(ValidationError, match="Answer value too long"):
            FormSubmitRequest(answers={"q1": "x" * 50001})

    def test_unsupported_value_type_dict(self):
        from app.schemas.form import FormSubmitRequest

        with pytest.raises(ValidationError, match="Unsupported answer value type"):
            FormSubmitRequest(answers={"q1": {"nested": "dict"}})

    def test_list_too_long(self):
        from app.schemas.form import FormSubmitRequest

        with pytest.raises(ValidationError, match="Answer list too long"):
            FormSubmitRequest(answers={"q1": ["x"] * 101})

    def test_list_non_string_items(self):
        from app.schemas.form import FormSubmitRequest

        with pytest.raises(ValidationError, match="Answer list items must be strings"):
            FormSubmitRequest(answers={"q1": [1, 2, 3]})

    def test_none_value_allowed(self):
        from app.schemas.form import FormSubmitRequest

        req = FormSubmitRequest(answers={"q1": None})
        assert req.answers["q1"] is None

    def test_numeric_values_allowed(self):
        from app.schemas.form import FormSubmitRequest

        req = FormSubmitRequest(answers={"q1": 42, "q2": 3.14})
        assert req.answers["q1"] == 42
        assert req.answers["q2"] == 3.14

    def test_200_keys_allowed(self):
        from app.schemas.form import FormSubmitRequest

        answers = {f"q{i}": "val" for i in range(200)}
        req = FormSubmitRequest(answers=answers)
        assert len(req.answers) == 200


# ---------------------------------------------------------------------------
# Helpers: auth override
# ---------------------------------------------------------------------------


def _override_auth(role="MEMBER"):
    from app.core.deps import get_current_user
    from app.main import app

    uid = str(uuid.uuid4())
    payload = {"sub": uid, "role": role, "jti": str(uuid.uuid4())}
    app.dependency_overrides[get_current_user] = lambda: payload
    return payload, uid


def _clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# M-34: SIG endpoint offset bounds
# ---------------------------------------------------------------------------


class TestSigOffsetBounds:
    """M-34: SIG endpoints reject offset > MAX_PAGE_NUMBER * 100."""

    @pytest.mark.anyio
    async def test_get_sigs_offset_too_large(self, client):
        try:
            _override_auth("MEMBER")
            resp = await client.get("/api/v1/sigs?offset=1000001")
            assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_get_sigs_offset_at_max(self, client):
        """Offset at exactly the max (1000000) should be accepted."""
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_SIG_EP}.list_sigs",
                new_callable=AsyncMock,
                return_value=([], 0),
            ):
                resp = await client.get("/api/v1/sigs?offset=1000000")
                assert resp.status_code == 200
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_get_sig_members_offset_too_large(self, client):
        try:
            _override_auth("MEMBER")
            sig_id = uuid.uuid4()
            resp = await client.get(f"/api/v1/sigs/{sig_id}/members?offset=1000001")
            assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_get_sig_members_offset_negative(self, client):
        try:
            _override_auth("MEMBER")
            sig_id = uuid.uuid4()
            resp = await client.get(f"/api/v1/sigs/{sig_id}/members?offset=-1")
            assert resp.status_code == 422
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# M-35: Admin user search max_length
# ---------------------------------------------------------------------------


class TestAdminSearchMaxLength:
    """M-35: search parameter rejects strings > 200 chars."""

    @pytest.mark.anyio
    async def test_search_too_long(self, client):
        try:
            _override_auth("SUPER_ADMIN")
            long_search = "x" * 201
            resp = await client.get(f"/api/v1/users?search={long_search}")
            assert resp.status_code == 422
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_search_at_max_length(self, client):
        try:
            _override_auth("SUPER_ADMIN")
            search = "x" * 200
            with patch(
                f"{_USERS_EP}.list_users",
                new_callable=AsyncMock,
                return_value=([], 0),
            ):
                resp = await client.get(f"/api/v1/users?search={search}")
                assert resp.status_code == 200
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# L-44: Cursor parsing returns generic 422 on invalid cursor
# ---------------------------------------------------------------------------


class TestCursorParsing:
    """L-44: Invalid cursor returns 422 with generic message, no internal details."""

    @pytest.mark.anyio
    async def test_invalid_cursor_returns_422(self, client):
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_POSTS_EP}.list_posts",
                new_callable=AsyncMock,
                side_effect=ValueError("Invalid cursor."),
            ):
                resp = await client.get("/api/v1/posts?cursor=not-valid-base64!!!")
                assert resp.status_code == 422
                body = resp.json()
                detail = body.get("detail", {})
                # detail may be a dict with 'message' or a string
                msg = (
                    detail.get("message", str(detail)) if isinstance(detail, dict) else str(detail)
                )
                assert "Invalid cursor" in msg
                assert "Traceback" not in msg
                assert "binascii" not in msg
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_malformed_base64_cursor(self, client):
        import base64

        bad = base64.urlsafe_b64encode(b"only_one_part").decode()
        try:
            _override_auth("MEMBER")
            with patch(
                f"{_POSTS_EP}.list_posts",
                new_callable=AsyncMock,
                side_effect=ValueError("Invalid cursor."),
            ):
                resp = await client.get(f"/api/v1/posts?cursor={bad}")
                assert resp.status_code == 422
        finally:
            _clear_overrides()

    def test_decode_cursor_no_internal_details(self):
        """_decode_cursor raises ValueError with generic message."""
        from app.repositories.post_repo import _decode_cursor

        with pytest.raises(ValueError, match="^Invalid cursor\\.$"):
            _decode_cursor("not-valid-base64")

    def test_decode_cursor_bad_format(self):
        import base64

        from app.repositories.post_repo import _decode_cursor

        bad = base64.urlsafe_b64encode(b"only_one_part").decode()
        with pytest.raises(ValueError, match="^Invalid cursor\\.$"):
            _decode_cursor(bad)


# ---------------------------------------------------------------------------
# M-47: Password change ValueError message sanitization
# ---------------------------------------------------------------------------


class TestPasswordChangeErrorSanitization:
    """M-47: Password change only passes through known-safe error messages."""

    @pytest.mark.anyio
    async def test_safe_password_error_passed_through(self, client):
        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_USERS_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_USERS_EP}.change_password",
                    new_callable=AsyncMock,
                    side_effect=ValueError("Password must be at least 12 characters."),
                ),
            ):
                resp = await client.put(
                    "/api/v1/users/me/password",
                    json={"current_password": "OldPass123!", "new_password": "NewPass123!"},
                )
                assert resp.status_code == 400
                assert "Password must be" in resp.json()["detail"]["message"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_unsafe_error_replaced_with_generic(self, client):
        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_USERS_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_USERS_EP}.change_password",
                    new_callable=AsyncMock,
                    side_effect=ValueError("relation 'users' does not exist"),
                ),
            ):
                resp = await client.put(
                    "/api/v1/users/me/password",
                    json={"current_password": "OldPass123!", "new_password": "NewPass123!"},
                )
                assert resp.status_code == 400
                body = resp.json()
                assert body["detail"]["message"] == "Invalid input."
                assert "relation" not in body["detail"]["message"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_current_password_error_passed_through(self, client):
        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_USERS_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_USERS_EP}.change_password",
                    new_callable=AsyncMock,
                    side_effect=ValueError("Current password is incorrect."),
                ),
            ):
                resp = await client.put(
                    "/api/v1/users/me/password",
                    json={"current_password": "WrongPass1!", "new_password": "NewPass123!"},
                )
                assert resp.status_code == 400
                assert "Current password" in resp.json()["detail"]["message"]
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_incorrect_prefix_passed_through(self, client):
        try:
            _override_auth("MEMBER")
            with (
                patch(f"{_USERS_EP}.check_rate_limit", new_callable=AsyncMock, return_value=True),
                patch(
                    f"{_USERS_EP}.change_password",
                    new_callable=AsyncMock,
                    side_effect=ValueError("Incorrect current password."),
                ),
            ):
                resp = await client.put(
                    "/api/v1/users/me/password",
                    json={"current_password": "WrongPass1!", "new_password": "NewPass123!"},
                )
                assert resp.status_code == 400
                assert "Incorrect" in resp.json()["detail"]["message"]
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# L-47: about.py avatar content-length parsing
# ---------------------------------------------------------------------------


class TestAboutAvatarContentLength:
    """L-47: int(content_length) wrapped in try/except."""

    @pytest.mark.anyio
    async def test_non_numeric_content_length_does_not_crash(self, client):
        """If upstream returns non-numeric content-length, should not raise."""
        contributor_id = uuid.uuid4()
        try:
            _override_auth("MEMBER")

            with (
                patch(
                    "app.api.v1.endpoints.about.contributor_service.get_contributor",
                    new_callable=AsyncMock,
                    return_value={
                        "id": contributor_id,
                        "github_username": "testuser",
                        "display_name": "Test",
                        "role": "Developer",
                    },
                ),
                patch(
                    "app.api.v1.endpoints.about.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch("asyncio.get_event_loop") as mock_loop,
            ):
                sync_resp = type(
                    "Resp",
                    (),
                    {
                        "status_code": 200,
                        "headers": {
                            "content-type": "image/png",
                            "content-length": "not-a-number",
                        },
                        "content": b"\x89PNG fake",
                    },
                )()
                mock_loop.return_value.run_in_executor = AsyncMock(return_value=sync_resp)

                resp = await client.get(f"/api/v1/about/contributors/{contributor_id}/avatar")
                # Should succeed (content-length parse failure -> 0, under limit)
                assert resp.status_code == 200
        finally:
            _clear_overrides()
