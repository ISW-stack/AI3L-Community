"""Tests for technical debt fixes: audit logging, sig_admin simplification,
find_members single-query, and centralized constants."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Helpers ──────────────────────────────────────────────────────────


def _override_auth(role: str = "MEMBER", user_id: str | None = None) -> dict:
    from app.core.deps import get_current_user
    from app.main import app

    uid = user_id or str(uuid.uuid4())
    payload = {"sub": uid, "role": role, "jti": str(uuid.uuid4())}
    app.dependency_overrides[get_current_user] = lambda: payload
    return payload


def _clear_overrides() -> None:
    from app.main import app

    app.dependency_overrides.clear()


# ── A1: Admin file deletion audit logging ────────────────────────────


class TestAdminFileDeletionAuditLogging:
    """DELETE /files/content/{key} by admin emits audit event."""

    @pytest.mark.anyio
    async def test_admin_delete_emits_audit_event(self, client) -> None:
        """When an admin deletes another user's file, an audit event is emitted."""
        admin_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        _override_auth("ADMIN", user_id=admin_id)
        file_key = f"editor/{owner_id}/somefile.png"
        file_size = 12345

        try:
            with (
                patch(
                    "app.api.v1.endpoints.files.async_get_file_size",
                    new_callable=AsyncMock,
                    return_value=file_size,
                ),
                patch(
                    "app.api.v1.endpoints.files.async_delete_file",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.api.v1.endpoints.files.user_repo.increment_storage_used",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.api.v1.endpoints.files.file_scan_repo.delete_by_key",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.core.event_bus.emit",
                    new_callable=AsyncMock,
                ) as mock_emit,
            ):
                resp = await client.delete(
                    f"/api/v1/files/content/{file_key}",
                    headers={"Authorization": "Bearer fake"},
                )

            assert resp.status_code == 200
            mock_emit.assert_called_once_with(
                "audit.action",
                action="admin_file_delete",
                actor_id=admin_id,
                target_key=file_key,
                file_size=file_size,
                owner_user_id=owner_id,
            )
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_owner_delete_emits_file_delete_audit(self, client) -> None:
        """When a user deletes their own file, a file_delete audit event is emitted."""
        user_id = str(uuid.uuid4())
        _override_auth("MEMBER", user_id=user_id)
        file_key = f"editor/{user_id}/myfile.png"
        file_size = 5000

        try:
            with (
                patch(
                    "app.api.v1.endpoints.files.async_get_file_size",
                    new_callable=AsyncMock,
                    return_value=file_size,
                ),
                patch(
                    "app.api.v1.endpoints.files.async_delete_file",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.api.v1.endpoints.files.user_repo.increment_storage_used",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.api.v1.endpoints.files.file_scan_repo.delete_by_key",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.core.event_bus.emit",
                    new_callable=AsyncMock,
                ) as mock_emit,
            ):
                resp = await client.delete(
                    f"/api/v1/files/content/{file_key}",
                    headers={"Authorization": "Bearer fake"},
                )

            assert resp.status_code == 200
            mock_emit.assert_called_once_with(
                "audit.action",
                action="file_delete",
                actor_id=user_id,
                target_key=file_key,
                file_size=file_size,
            )
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_admin_delete_own_file_emits_file_delete_audit(self, client) -> None:
        """When an admin deletes their own file, a file_delete
        (not admin_file_delete) event is emitted."""
        admin_id = str(uuid.uuid4())
        _override_auth("ADMIN", user_id=admin_id)
        file_key = f"editor/{admin_id}/myfile.png"
        file_size = 7000

        try:
            with (
                patch(
                    "app.api.v1.endpoints.files.async_get_file_size",
                    new_callable=AsyncMock,
                    return_value=file_size,
                ),
                patch(
                    "app.api.v1.endpoints.files.async_delete_file",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.api.v1.endpoints.files.user_repo.increment_storage_used",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.api.v1.endpoints.files.file_scan_repo.delete_by_key",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.core.event_bus.emit",
                    new_callable=AsyncMock,
                ) as mock_emit,
            ):
                resp = await client.delete(
                    f"/api/v1/files/content/{file_key}",
                    headers={"Authorization": "Bearer fake"},
                )

            assert resp.status_code == 200
            mock_emit.assert_called_once_with(
                "audit.action",
                action="file_delete",
                actor_id=admin_id,
                target_key=file_key,
                file_size=file_size,
            )
        finally:
            _clear_overrides()

    @pytest.mark.anyio
    async def test_audit_event_failure_does_not_break_deletion(self, client) -> None:
        """If audit event emission fails, the file deletion still succeeds."""
        admin_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        _override_auth("ADMIN", user_id=admin_id)
        file_key = f"editor/{owner_id}/file.png"
        file_size = 9999

        try:
            with (
                patch(
                    "app.api.v1.endpoints.files.async_get_file_size",
                    new_callable=AsyncMock,
                    return_value=file_size,
                ),
                patch(
                    "app.api.v1.endpoints.files.async_delete_file",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.api.v1.endpoints.files.user_repo.increment_storage_used",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.api.v1.endpoints.files.file_scan_repo.delete_by_key",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.core.event_bus.emit",
                    new_callable=AsyncMock,
                    side_effect=RuntimeError("Redis down"),
                ),
            ):
                resp = await client.delete(
                    f"/api/v1/files/content/{file_key}",
                    headers={"Authorization": "Bearer fake"},
                )

            assert resp.status_code == 200
            assert resp.json()["freed_bytes"] == file_size
        finally:
            _clear_overrides()


# ── A3: require_sig_admin simplified signature ───────────────────────


class TestRequireSigAdminSimplified:
    """require_sig_admin() works without the removed sig_id_param parameter."""

    @pytest.mark.anyio
    async def test_platform_admin_passes(self) -> None:
        """Platform ADMIN bypasses SIG role check."""
        from app.dependencies.sig_admin import require_sig_admin

        dep = require_sig_admin()
        sig_id = uuid.uuid4()
        current_user = {"sub": str(uuid.uuid4()), "role": "ADMIN", "jti": "x"}

        result = await dep(sig_id=sig_id, current_user=current_user)
        assert result is current_user

    @pytest.mark.anyio
    async def test_super_admin_passes(self) -> None:
        """Platform SUPER_ADMIN bypasses SIG role check."""
        from app.dependencies.sig_admin import require_sig_admin

        dep = require_sig_admin()
        sig_id = uuid.uuid4()
        current_user = {"sub": str(uuid.uuid4()), "role": "SUPER_ADMIN", "jti": "x"}

        result = await dep(sig_id=sig_id, current_user=current_user)
        assert result is current_user

    @pytest.mark.anyio
    async def test_sig_admin_passes(self) -> None:
        """User with SIG ADMIN role passes."""
        from app.dependencies.sig_admin import require_sig_admin

        dep = require_sig_admin()
        sig_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        current_user = {"sub": user_id, "role": "MEMBER", "jti": "x"}

        with patch(
            "app.dependencies.sig_admin.sig_repo.get_member_role",
            new_callable=AsyncMock,
            return_value="ADMIN",
        ):
            result = await dep(sig_id=sig_id, current_user=current_user)

        assert result is current_user

    @pytest.mark.anyio
    async def test_sig_sub_admin_passes(self) -> None:
        """User with SIG SUB_ADMIN role passes."""
        from app.dependencies.sig_admin import require_sig_admin

        dep = require_sig_admin()
        sig_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        current_user = {"sub": user_id, "role": "MEMBER", "jti": "x"}

        with patch(
            "app.dependencies.sig_admin.sig_repo.get_member_role",
            new_callable=AsyncMock,
            return_value="SUB_ADMIN",
        ):
            result = await dep(sig_id=sig_id, current_user=current_user)

        assert result is current_user

    @pytest.mark.anyio
    async def test_regular_member_rejected(self) -> None:
        """Regular SIG MEMBER gets HTTP 403."""
        from fastapi import HTTPException

        from app.dependencies.sig_admin import require_sig_admin

        dep = require_sig_admin()
        sig_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        current_user = {"sub": user_id, "role": "MEMBER", "jti": "x"}

        with patch(
            "app.dependencies.sig_admin.sig_repo.get_member_role",
            new_callable=AsyncMock,
            return_value="MEMBER",
        ):
            with pytest.raises(HTTPException) as exc_info:
                await dep(sig_id=sig_id, current_user=current_user)
            assert exc_info.value.status_code == 403

    @pytest.mark.anyio
    async def test_non_member_rejected(self) -> None:
        """Non-member (no SIG role) gets HTTP 403."""
        from fastapi import HTTPException

        from app.dependencies.sig_admin import require_sig_admin

        dep = require_sig_admin()
        sig_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        current_user = {"sub": user_id, "role": "MEMBER", "jti": "x"}

        with patch(
            "app.dependencies.sig_admin.sig_repo.get_member_role",
            new_callable=AsyncMock,
            return_value=None,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await dep(sig_id=sig_id, current_user=current_user)
            assert exc_info.value.status_code == 403

    def test_no_parameters_accepted(self) -> None:
        """require_sig_admin() takes no arguments (sig_id_param removed)."""
        import inspect

        from app.dependencies.sig_admin import require_sig_admin

        sig = inspect.signature(require_sig_admin)
        assert len(sig.parameters) == 0


# ── C6: find_members single-query pattern ────────────────────────────


class TestFindMembersSingleQuery:
    """sig_repo.find_members() uses COUNT(*) OVER() single-query pattern."""

    @pytest.mark.anyio
    async def test_returns_items_and_total(self, mock_pool, mock_conn) -> None:
        """find_members returns (items, total) with correct total from window fn."""
        from app.repositories import sig_repo

        sig_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        user_id_1 = uuid.uuid4()
        user_id_2 = uuid.uuid4()

        rows = [
            {
                "id": uuid.uuid4(),
                "sig_id": sig_id,
                "user_id": user_id_1,
                "role": "ADMIN",
                "created_at": now,
                "updated_at": now,
                "display_name": "User1",
                "username": "user1",
                "avatar_url": None,
                "_total": 5,
            },
            {
                "id": uuid.uuid4(),
                "sig_id": sig_id,
                "user_id": user_id_2,
                "role": "MEMBER",
                "created_at": now,
                "updated_at": now,
                "display_name": "User2",
                "username": "user2",
                "avatar_url": "avatars/test.png",
                "_total": 5,
            },
        ]
        mock_conn.fetch = AsyncMock(return_value=rows)

        with patch("app.repositories.sig_repo.get_pool", return_value=mock_pool):
            items, total = await sig_repo.find_members(sig_id, offset=0, limit=2)

        assert total == 5
        assert len(items) == 2
        assert items[0]["display_name"] == "User1"
        assert items[1]["username"] == "user2"
        # _total should be stripped from returned items
        assert "_total" not in items[0]
        assert "_total" not in items[1]

    @pytest.mark.anyio
    async def test_empty_result(self, mock_pool, mock_conn) -> None:
        """find_members returns ([], 0) when no members exist."""
        from app.repositories import sig_repo

        sig_id = uuid.uuid4()
        mock_conn.fetch = AsyncMock(return_value=[])

        with patch("app.repositories.sig_repo.get_pool", return_value=mock_pool):
            items, total = await sig_repo.find_members(sig_id)

        assert items == []
        assert total == 0

    @pytest.mark.anyio
    async def test_single_member(self, mock_pool, mock_conn) -> None:
        """find_members works correctly with exactly one member."""
        from app.repositories import sig_repo

        sig_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        rows = [
            {
                "id": uuid.uuid4(),
                "sig_id": sig_id,
                "user_id": uuid.uuid4(),
                "role": "ADMIN",
                "created_at": now,
                "updated_at": now,
                "display_name": "SoloUser",
                "username": "solo",
                "avatar_url": None,
                "_total": 1,
            },
        ]
        mock_conn.fetch = AsyncMock(return_value=rows)

        with patch("app.repositories.sig_repo.get_pool", return_value=mock_pool):
            items, total = await sig_repo.find_members(sig_id, offset=0, limit=50)

        assert total == 1
        assert len(items) == 1
        assert items[0]["display_name"] == "SoloUser"
        assert "_total" not in items[0]

    @pytest.mark.anyio
    async def test_single_query_executed(self, mock_pool, mock_conn) -> None:
        """find_members executes only one query (fetch), not fetchval + fetch."""
        from app.repositories import sig_repo

        sig_id = uuid.uuid4()
        mock_conn.fetch = AsyncMock(return_value=[])

        with patch("app.repositories.sig_repo.get_pool", return_value=mock_pool):
            await sig_repo.find_members(sig_id)

        # Only conn.fetch should be called, not conn.fetchval
        mock_conn.fetch.assert_called_once()
        mock_conn.fetchval.assert_not_called()

    @pytest.mark.anyio
    async def test_pagination_params_passed(self, mock_pool, mock_conn) -> None:
        """find_members passes offset and limit to the query."""
        from app.repositories import sig_repo

        sig_id = uuid.uuid4()
        mock_conn.fetch = AsyncMock(return_value=[])

        with patch("app.repositories.sig_repo.get_pool", return_value=mock_pool):
            await sig_repo.find_members(sig_id, offset=10, limit=25)

        call_args = mock_conn.fetch.call_args
        # positional args: (query, sig_id, limit, offset)
        assert call_args.args[1] == sig_id
        assert call_args.args[2] == 25  # limit
        assert call_args.args[3] == 10  # offset


# ── C11: Centralized constants ───────────────────────────────────────


class TestCentralizedConstants:
    """Verify centralized constants exist and have correct values."""

    def test_pagination_defaults(self) -> None:
        from app.core.constants import (
            DEFAULT_PAGE_SIZE,
            DEFAULT_PAGE_SIZE_COMMENTS,
            DEFAULT_PAGE_SIZE_FORMS,
            DEFAULT_PAGE_SIZE_MEMBERS,
            DEFAULT_PAGE_SIZE_NOTIFICATIONS,
            DEFAULT_PAGE_SIZE_POSTS,
            MAX_PAGE_NUMBER,
            MAX_PAGE_SIZE,
        )

        assert DEFAULT_PAGE_SIZE == 20
        assert DEFAULT_PAGE_SIZE_POSTS == 20
        assert DEFAULT_PAGE_SIZE_COMMENTS == 20
        assert DEFAULT_PAGE_SIZE_MEMBERS == 20
        assert DEFAULT_PAGE_SIZE_FORMS == 20
        assert DEFAULT_PAGE_SIZE_NOTIFICATIONS == 20
        assert MAX_PAGE_SIZE == 100
        assert MAX_PAGE_NUMBER == 10000

    def test_field_length_limits(self) -> None:
        from app.core.constants import (
            MAX_AFFILIATION_LENGTH,
            MAX_BIO_LENGTH,
            MAX_DISPLAY_NAME_LENGTH,
            MAX_KEYWORD_LENGTH,
            MAX_ORCID_LENGTH,
        )

        assert MAX_BIO_LENGTH == 500
        assert MAX_DISPLAY_NAME_LENGTH == 100
        assert MAX_AFFILIATION_LENGTH == 200
        assert MAX_ORCID_LENGTH == 30
        assert MAX_KEYWORD_LENGTH == 50

    def test_post_history_limit(self) -> None:
        from app.core.constants import POST_HISTORY_LIMIT

        assert POST_HISTORY_LIMIT == 50

    def test_avatar_cache_constants(self) -> None:
        from app.core.constants import AVATAR_CACHE_MAX_SIZE, AVATAR_CACHE_TTL_SECONDS

        assert AVATAR_CACHE_MAX_SIZE == 50
        assert AVATAR_CACHE_TTL_SECONDS == 3600


# ===========================================================================
# C7: Form question schema validation
# ===========================================================================


class TestQuestionSchemaValidation:
    """Validate form question structure before saving to JSONB."""

    def _validate(self, questions):
        from app.services.form import validate_question_schema

        return validate_question_schema(questions)

    def test_valid_text_question_passes(self):
        self._validate([{"id": "q1", "type": "text", "label": "Name"}])

    def test_valid_textarea_question_passes(self):
        self._validate([{"id": "q1", "type": "textarea", "label": "Bio"}])

    def test_valid_rating_question_passes(self):
        self._validate([{"id": "q1", "type": "rating", "label": "Rate us"}])

    def test_valid_single_choice_with_options_passes(self):
        self._validate(
            [
                {
                    "id": "q1",
                    "type": "single_choice",
                    "label": "Pick one",
                    "options": [{"id": "o1", "label": "A"}],
                }
            ]
        )

    def test_valid_multiple_choice_with_options_passes(self):
        self._validate(
            [
                {
                    "id": "q1",
                    "type": "multiple_choice",
                    "label": "Pick many",
                    "options": [{"id": "o1", "label": "A"}, {"id": "o2", "label": "B"}],
                }
            ]
        )

    def test_valid_dropdown_with_options_passes(self):
        self._validate(
            [
                {
                    "id": "q1",
                    "type": "dropdown",
                    "label": "Select",
                    "options": [{"id": "o1", "label": "A"}],
                }
            ]
        )

    def test_missing_id_raises(self):
        with pytest.raises(ValueError, match="missing required field 'id'"):
            self._validate([{"type": "text", "label": "Name"}])

    def test_missing_type_raises(self):
        with pytest.raises(ValueError, match="missing required field 'type'"):
            self._validate([{"id": "q1", "label": "Name"}])

    def test_missing_label_raises(self):
        with pytest.raises(ValueError, match="missing required field 'label'"):
            self._validate([{"id": "q1", "type": "text"}])

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="invalid type 'checkbox'"):
            self._validate([{"id": "q1", "type": "checkbox", "label": "Bad"}])

    def test_single_choice_missing_options_raises(self):
        with pytest.raises(ValueError, match="must have an 'options' list"):
            self._validate([{"id": "q1", "type": "single_choice", "label": "Pick"}])

    def test_multiple_choice_missing_options_raises(self):
        with pytest.raises(ValueError, match="must have an 'options' list"):
            self._validate([{"id": "q1", "type": "multiple_choice", "label": "Pick"}])

    def test_dropdown_missing_options_raises(self):
        with pytest.raises(ValueError, match="must have an 'options' list"):
            self._validate([{"id": "q1", "type": "dropdown", "label": "Pick"}])

    def test_single_choice_empty_options_raises(self):
        with pytest.raises(ValueError, match="must have at least one option"):
            self._validate([{"id": "q1", "type": "single_choice", "label": "Pick", "options": []}])

    def test_duplicate_question_id_raises(self):
        with pytest.raises(ValueError, match="Duplicate question id 'q1'"):
            self._validate(
                [
                    {"id": "q1", "type": "text", "label": "Name"},
                    {"id": "q1", "type": "text", "label": "Other"},
                ]
            )

    def test_non_dict_question_raises(self):
        with pytest.raises(ValueError, match="must be an object"):
            self._validate(["not a dict"])

    def test_non_list_raises(self):
        with pytest.raises(ValueError, match="must be a list"):
            self._validate("not a list")

    def test_multiple_valid_questions_pass(self):
        self._validate(
            [
                {"id": "q1", "type": "text", "label": "Name"},
                {"id": "q2", "type": "rating", "label": "Rate"},
                {
                    "id": "q3",
                    "type": "dropdown",
                    "label": "Choose",
                    "options": [{"id": "o1", "label": "A"}],
                },
            ]
        )

    def test_options_not_a_list_raises(self):
        with pytest.raises(ValueError, match="must have an 'options' list"):
            self._validate(
                [{"id": "q1", "type": "single_choice", "label": "Pick", "options": "bad"}]
            )


# ===========================================================================
# C8: User profile field length validation
# ===========================================================================


class TestProfileFieldLengthValidation:
    """Validate profile field lengths at the service layer."""

    def _validate(self, **kwargs):
        from app.services.user import _validate_profile_field_lengths

        return _validate_profile_field_lengths(**kwargs)

    def test_valid_lengths_pass(self):
        self._validate(
            display_name="Alice",
            bio="Short bio",
            affiliation="MIT",
            orcid="0000-0001-2345-6789",
        )

    def test_none_values_pass(self):
        self._validate(display_name=None, bio=None, affiliation=None, orcid=None)

    def test_display_name_too_long_raises(self):
        with pytest.raises(ValueError, match="display_name must be at most 100"):
            self._validate(display_name="x" * 101)

    def test_display_name_exactly_at_limit_passes(self):
        self._validate(display_name="x" * 100)

    def test_bio_too_long_raises(self):
        with pytest.raises(ValueError, match="bio must be at most 500"):
            self._validate(bio="x" * 501)

    def test_bio_exactly_at_limit_passes(self):
        self._validate(bio="x" * 500)

    def test_affiliation_too_long_raises(self):
        with pytest.raises(ValueError, match="affiliation must be at most 200"):
            self._validate(affiliation="x" * 201)

    def test_affiliation_exactly_at_limit_passes(self):
        self._validate(affiliation="x" * 200)

    def test_orcid_too_long_raises(self):
        with pytest.raises(ValueError, match="orcid must be at most 30"):
            self._validate(orcid="x" * 31)

    def test_orcid_exactly_at_limit_passes(self):
        self._validate(orcid="x" * 30)

    @pytest.mark.anyio
    async def test_update_user_profile_rejects_long_bio(self):
        """update_user_profile should raise ValueError before hitting the DB."""
        from app.services.user import update_user_profile

        with pytest.raises(ValueError, match="bio must be at most 500"):
            await update_user_profile(uuid.uuid4(), bio="x" * 501)

    @pytest.mark.anyio
    async def test_update_user_profile_rejects_long_display_name(self):
        from app.services.user import update_user_profile

        with pytest.raises(ValueError, match="display_name must be at most 100"):
            await update_user_profile(uuid.uuid4(), display_name="x" * 101)


# ===========================================================================
# C13: get_pool_stats() helper
# ===========================================================================


class TestGetPoolStats:
    """Test the database pool stats helper function."""

    @pytest.mark.anyio
    async def test_returns_none_when_pool_not_initialized(self):
        from app.core.database import get_pool_stats

        with patch("app.core.database._pool", None):
            result = await get_pool_stats()
            assert result is None

    @pytest.mark.anyio
    async def test_returns_stats_when_pool_initialized(self):
        from app.core.database import get_pool_stats

        mock_pool = MagicMock()
        mock_pool.get_size.return_value = 10
        mock_pool.get_idle_size.return_value = 7

        with patch("app.core.database._pool", mock_pool):
            result = await get_pool_stats()

        assert result is not None
        assert result["size"] == 10
        assert result["free"] == 7
        assert result["in_use"] == 3

    @pytest.mark.anyio
    async def test_returns_correct_structure(self):
        from app.core.database import get_pool_stats

        mock_pool = MagicMock()
        mock_pool.get_size.return_value = 30
        mock_pool.get_idle_size.return_value = 30

        with patch("app.core.database._pool", mock_pool):
            result = await get_pool_stats()

        assert set(result.keys()) == {"size", "free", "in_use"}
        assert result["in_use"] == 0

    @pytest.mark.anyio
    async def test_in_use_when_all_busy(self):
        from app.core.database import get_pool_stats

        mock_pool = MagicMock()
        mock_pool.get_size.return_value = 5
        mock_pool.get_idle_size.return_value = 0

        with patch("app.core.database._pool", mock_pool):
            result = await get_pool_stats()

        assert result["in_use"] == 5


# ===========================================================================
# C3: Post file cleanup failure tracking and logging
# ===========================================================================


class TestCleanupPostFilesLogging:
    """_cleanup_post_files should track and log succeeded/failed file deletions."""

    @pytest.mark.anyio
    async def test_cleanup_logs_failure_summary(self):
        """When some files fail to delete, a summary is logged."""
        from app.services.post import _cleanup_post_files

        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        content = (
            '<img src="/api/v1/files/content/editor/file1.png">'
            '<img src="/api/v1/files/content/editor/file2.png">'
        )

        async def fake_get_file_size(key):
            return 1024

        async def fake_delete_file(key):
            if "file2" in key:
                raise RuntimeError("Storage error")

        with (
            patch(
                "app.repositories.post_repo.find_content_by_id",
                new_callable=AsyncMock,
                return_value=content,
            ),
            patch(
                "app.core.async_storage.delete_file",
                side_effect=fake_delete_file,
            ),
            patch(
                "app.core.async_storage.get_file_size",
                side_effect=fake_get_file_size,
            ),
            patch("app.repositories.user_repo.decrement_storage_used", new_callable=AsyncMock),
            patch("app.services.post.logger") as mock_logger,
        ):
            await _cleanup_post_files(post_id, user_id)

            # Should log a summary with succeeded and failed counts
            summary_calls = [
                c for c in mock_logger.warning.call_args_list if "summary" in str(c).lower()
            ]
            assert len(summary_calls) >= 1
            summary_extra = summary_calls[0].kwargs.get("extra", {})
            assert summary_extra["succeeded"] == 1
            assert summary_extra["failed"] == 1

    @pytest.mark.anyio
    async def test_cleanup_no_summary_when_all_succeed(self):
        """When all files delete successfully, no failure summary is logged."""
        from app.services.post import _cleanup_post_files

        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        content = '<img src="/api/v1/files/content/editor/file1.png">'

        with (
            patch(
                "app.repositories.post_repo.find_content_by_id",
                new_callable=AsyncMock,
                return_value=content,
            ),
            patch("app.core.async_storage.delete_file", new_callable=AsyncMock),
            patch(
                "app.core.async_storage.get_file_size",
                new_callable=AsyncMock,
                return_value=512,
            ),
            patch("app.repositories.user_repo.decrement_storage_used", new_callable=AsyncMock),
            patch("app.services.post.logger") as mock_logger,
        ):
            await _cleanup_post_files(post_id, user_id)

            # No summary log when all succeed
            summary_calls = [
                c for c in mock_logger.warning.call_args_list if "summary" in str(c).lower()
            ]
            assert len(summary_calls) == 0


# ===========================================================================
# C14: Malformed rating values logged
# ===========================================================================


class TestMalformedRatingLogging:
    """get_form_stats should log warnings for non-integer rating values."""

    def _make_form_row(self, questions):
        now = datetime.now(timezone.utc)
        return {
            "id": uuid.uuid4(),
            "sig_id": uuid.uuid4(),
            "title": "Test",
            "description": None,
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": questions,
            "is_schema_locked": False,
            "allow_non_members": False,
            "is_deleted": False,
            "created_by": uuid.uuid4(),
            "created_at": now,
            "updated_at": now,
        }

    @pytest.mark.anyio
    async def test_malformed_rating_is_logged(self):
        """A string value for a rating question should trigger a logger.warning."""
        from app.services.form import get_form_stats

        form_id = uuid.uuid4()
        questions = [{"id": "q1", "type": "rating", "label": "Rate us"}]
        form_row = self._make_form_row(questions)

        responses = [
            {"answers": {"q1": 4}},  # valid
            {"answers": {"q1": "five"}},  # malformed
            {"answers": {"q1": 3}},  # valid
        ]

        with (
            patch(
                "app.services.form.form_repo.find_by_id",
                new_callable=AsyncMock,
                return_value=(form_row, 3),
            ),
            patch(
                "app.services.form.form_repo.find_all_responses",
                new_callable=AsyncMock,
                return_value=responses,
            ),
            patch("app.services.form.logger") as mock_logger,
        ):
            result = await get_form_stats(form_id)

        # Stats should only include the 2 valid integer values
        rating_stats = result["question_stats"][0]["stats"]
        assert rating_stats["count"] == 2
        assert rating_stats["average"] == 3.5

        # Warning should have been logged for the malformed value
        mock_logger.warning.assert_called()
        warning_call = mock_logger.warning.call_args
        assert "Malformed rating" in warning_call[0][0]
        assert warning_call.kwargs["extra"]["value"] == repr("five")

    @pytest.mark.anyio
    async def test_boolean_rating_is_logged_as_malformed(self):
        """A boolean value for a rating question should be logged as malformed."""
        from app.services.form import get_form_stats

        form_id = uuid.uuid4()
        questions = [{"id": "q1", "type": "rating", "label": "Rate"}]
        form_row = self._make_form_row(questions)

        responses = [
            {"answers": {"q1": True}},  # malformed
        ]

        with (
            patch(
                "app.services.form.form_repo.find_by_id",
                new_callable=AsyncMock,
                return_value=(form_row, 1),
            ),
            patch(
                "app.services.form.form_repo.find_all_responses",
                new_callable=AsyncMock,
                return_value=responses,
            ),
            patch("app.services.form.logger") as mock_logger,
        ):
            result = await get_form_stats(form_id)

        rating_stats = result["question_stats"][0]["stats"]
        assert rating_stats["count"] == 0  # bool excluded

        mock_logger.warning.assert_called_once()
        assert "bool" in mock_logger.warning.call_args.kwargs["extra"]["value_type"]

    @pytest.mark.anyio
    async def test_none_rating_not_logged(self):
        """None rating values should not trigger a warning."""
        from app.services.form import get_form_stats

        form_id = uuid.uuid4()
        questions = [{"id": "q1", "type": "rating", "label": "Rate"}]
        form_row = self._make_form_row(questions)

        responses = [
            {"answers": {"q1": None}},
            {"answers": {}},
        ]

        with (
            patch(
                "app.services.form.form_repo.find_by_id",
                new_callable=AsyncMock,
                return_value=(form_row, 2),
            ),
            patch(
                "app.services.form.form_repo.find_all_responses",
                new_callable=AsyncMock,
                return_value=responses,
            ),
            patch("app.services.form.logger") as mock_logger,
        ):
            await get_form_stats(form_id)

        mock_logger.warning.assert_not_called()


# ===========================================================================
# C1: main.py — ddtrace exception handling
# ===========================================================================


class TestDdtraceExceptionHandling:
    """Verify that the ddtrace import block handles ImportError vs other exceptions."""

    def test_main_module_importable(self):
        """main.py should be importable regardless of ddtrace availability."""
        import app.main  # noqa: F401


# ===========================================================================
# C15: main.py — limit_request_body_size type hint
# ===========================================================================


class TestLimitRequestBodySizeTyping:
    """Verify the middleware function has proper type annotations."""

    def test_call_next_parameter_typed(self):
        """limit_request_body_size should have call_next typed (no type:ignore)."""
        import inspect

        from app.main import limit_request_body_size

        sig = inspect.signature(limit_request_body_size)
        params = sig.parameters
        assert "call_next" in params
        # Should have an annotation (not inspect.Parameter.empty)
        assert params["call_next"].annotation is not inspect.Parameter.empty


# ===========================================================================
# C5: Admin endpoint audit log error handling
# ===========================================================================


class TestAdminAuditLogErrorHandling:
    """Audit log emit failures should not crash admin endpoints."""

    def _do_override_auth(self, role="ADMIN", user_id=None):
        from app.core.deps import get_current_user
        from app.main import app

        uid = user_id or str(uuid.uuid4())
        payload = {"sub": uid, "role": role, "jti": str(uuid.uuid4())}
        app.dependency_overrides[get_current_user] = lambda: payload
        return payload, uid

    def _do_clear_overrides(self):
        from app.main import app

        app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_revoke_succeeds_when_audit_emit_fails(self, client):
        """PATCH /admin/invite-codes/{id}/revoke returns 200 even if audit emit fails."""
        code_id = uuid.uuid4()
        try:
            self._do_override_auth("ADMIN")
            with (
                patch(
                    "app.repositories.invite_code_repo.revoke",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    "app.core.event_bus.emit",
                    new_callable=AsyncMock,
                    side_effect=RuntimeError("event bus down"),
                ),
            ):
                resp = await client.patch(
                    f"/api/v1/admin/invite-codes/{code_id}/revoke",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["message"] == "Invite code revoked."
        finally:
            self._do_clear_overrides()

    @pytest.mark.anyio
    async def test_delete_succeeds_when_audit_emit_fails(self, client):
        """DELETE /admin/invite-codes/{id} returns 204 even if audit emit fails."""
        code_id = uuid.uuid4()
        try:
            self._do_override_auth("ADMIN")
            with (
                patch(
                    "app.repositories.invite_code_repo.delete",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    "app.core.event_bus.emit",
                    new_callable=AsyncMock,
                    side_effect=RuntimeError("event bus down"),
                ),
            ):
                resp = await client.delete(
                    f"/api/v1/admin/invite-codes/{code_id}",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 204
        finally:
            self._do_clear_overrides()


# ===========================================================================
# C4: Avatar storage counter rollback
# ===========================================================================


class TestAvatarStorageRollback:
    """When increment_storage_used fails, the uploaded file should be deleted."""

    @pytest.mark.anyio
    async def test_rollback_deletes_file_on_storage_counter_failure(self):
        """If increment_storage_used raises, the uploaded avatar should be deleted."""
        from app.services.user import upload_user_avatar

        user_id = str(uuid.uuid4())
        user_uuid = uuid.UUID(user_id)
        data = b"\x89PNG" + b"\x00" * 100
        content_type = "image/png"
        filename = "avatar.png"

        existing_user = {
            "id": user_uuid,
            "avatar_url": None,
        }

        updated_user = {
            "id": user_uuid,
            "username": "testuser",
            "display_name": "Test",
            "avatar_url": f"avatars/{user_id}/avatar.png",
            "role": "MEMBER",
            "bio": None,
            "affiliation": None,
            "orcid": None,
            "is_deleted": False,
            "is_banned": False,
            "ban_reason": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        mock_delete = AsyncMock()

        with (
            patch("app.services.user.validate_avatar"),
            patch("app.services.user.get_redis") as mock_get_redis,
            patch(
                "app.services.user.user_repo.find_by_id",
                new_callable=AsyncMock,
                return_value=existing_user,
            ),
            patch(
                "app.services.user.user_repo.get_storage_used",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch("app.services.user.async_upload_file", new_callable=AsyncMock),
            patch(
                "app.services.user.user_repo.increment_storage_used",
                new_callable=AsyncMock,
                side_effect=RuntimeError("DB error"),
            ),
            patch("app.services.user.async_delete_file", mock_delete),
            patch("app.services.user.generate_avatar_key", return_value="avatars/test.png"),
            patch(
                "app.services.user.update_user_profile",
                new_callable=AsyncMock,
                return_value=updated_user,
            ),
        ):
            mock_redis = AsyncMock()
            mock_redis.set = AsyncMock(return_value=True)
            mock_redis.delete = AsyncMock()
            mock_get_redis.return_value = mock_redis

            await upload_user_avatar(user_id, data, content_type, filename)

            # The rollback should have attempted to delete the uploaded file
            mock_delete.assert_any_call("avatars/test.png")


# ===========================================================================
# C2: Event handlers — transient vs permanent error logging
# ===========================================================================


class TestEventHandlerErrorDistinction:
    """Event handlers should distinguish transient from permanent errors."""

    @pytest.mark.anyio
    async def test_transient_error_logged_as_warning(self):
        """ConnectionError should be logged as a warning (transient)."""
        from app.event_handlers import _on_comment_created

        with (
            patch(
                "app.event_handlers._check_idempotent",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.services.notification.create_notification",
                new_callable=AsyncMock,
                side_effect=ConnectionError("DB connection lost"),
            ),
            patch("app.event_handlers.logger") as mock_logger,
        ):
            await _on_comment_created(
                user_id="u1",
                commenter_name="Alice",
                mention_targets=[("u2", "c1")],
                reply_target=None,
            )
            # Should use warning for transient errors
            mock_logger.warning.assert_called()
            assert "Transient" in mock_logger.warning.call_args[0][0]

    @pytest.mark.anyio
    async def test_permanent_error_logged_as_error(self):
        """Non-transient exceptions should still be logged as error."""
        from app.event_handlers import _on_comment_created

        with (
            patch(
                "app.event_handlers._check_idempotent",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.services.notification.create_notification",
                new_callable=AsyncMock,
                side_effect=ValueError("Bad data"),
            ),
            patch("app.event_handlers.logger") as mock_logger,
        ):
            await _on_comment_created(
                user_id="u1",
                commenter_name="Alice",
                mention_targets=[("u2", "c1")],
                reply_target=None,
            )
            # Should use error for permanent errors
            mock_logger.error.assert_called()
            error_messages = [c[0][0] for c in mock_logger.error.call_args_list]
            assert any("Failed to send mention" in m for m in error_messages)

    @pytest.mark.anyio
    async def test_reply_transient_error_logged_as_warning(self):
        """Transient error on reply notification should be logged as warning."""
        from app.event_handlers import _on_comment_created

        with (
            patch(
                "app.event_handlers._check_idempotent",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.services.notification.create_notification",
                new_callable=AsyncMock,
                side_effect=OSError("Network error"),
            ),
            patch("app.event_handlers.logger") as mock_logger,
        ):
            await _on_comment_created(
                user_id="u1",
                commenter_name="Bob",
                mention_targets=[],
                reply_target=("u3", "c2"),
            )
            mock_logger.warning.assert_called()
            assert "Transient" in mock_logger.warning.call_args[0][0]
