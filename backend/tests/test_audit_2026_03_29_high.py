"""Tests for HIGH-priority audit fixes (2026-03-29).

Covers: C-01, H-01, H-02, H-03, H-04, H-05.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_SVC_FORM = "app.services.form"
_EP_POSTS = "app.api.v1.endpoints.posts"


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


# ---------------------------------------------------------------------------
# C-01: ADMIN role post deletion treated as non-admin
# ---------------------------------------------------------------------------


class TestC01AdminPostDeletion:
    @pytest.mark.asyncio
    async def test_admin_is_admin_flag_true(self, client):
        """ADMIN users should have is_admin=True when deleting posts."""
        post_id = str(uuid.uuid4())
        try:
            _override_auth("ADMIN")
            with (
                patch(
                    f"{_EP_POSTS}.soft_delete_post",
                    new_callable=AsyncMock,
                    return_value=True,
                ) as mock_delete,
                patch(f"{_EP_POSTS}.emit", new_callable=AsyncMock),
            ):
                resp = await client.delete(f"/api/v1/posts/{post_id}")
                assert resp.status_code == 204
                mock_delete.assert_awaited_once()
                _, kwargs = mock_delete.call_args
                assert kwargs.get("is_admin") is True
        finally:
            _clear_overrides()

    @pytest.mark.asyncio
    async def test_member_is_admin_flag_false(self, client):
        """MEMBER users should have is_admin=False when deleting posts."""
        post_id = str(uuid.uuid4())
        try:
            _override_auth("MEMBER")
            with (
                patch(
                    f"{_EP_POSTS}.soft_delete_post",
                    new_callable=AsyncMock,
                    return_value=True,
                ) as mock_delete,
                patch(f"{_EP_POSTS}.emit", new_callable=AsyncMock),
            ):
                resp = await client.delete(f"/api/v1/posts/{post_id}")
                assert resp.status_code == 204
                mock_delete.assert_awaited_once()
                _, kwargs = mock_delete.call_args
                assert kwargs.get("is_admin") is False
        finally:
            _clear_overrides()

    @pytest.mark.asyncio
    async def test_super_admin_is_admin_flag_true(self, client):
        """SUPER_ADMIN users should have is_admin=True when deleting posts."""
        post_id = str(uuid.uuid4())
        try:
            _override_auth("SUPER_ADMIN")
            with (
                patch(
                    f"{_EP_POSTS}.soft_delete_post",
                    new_callable=AsyncMock,
                    return_value=True,
                ) as mock_delete,
                patch(f"{_EP_POSTS}.emit", new_callable=AsyncMock),
            ):
                resp = await client.delete(f"/api/v1/posts/{post_id}")
                assert resp.status_code == 204
                mock_delete.assert_awaited_once()
                _, kwargs = mock_delete.call_args
                assert kwargs.get("is_admin") is True
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# H-01: Guest form submissions bypass all file validation
# ---------------------------------------------------------------------------


class TestH01GuestFileValidation:
    @pytest.mark.asyncio
    async def test_guest_file_upload_scan_status_checked(self):
        """Guest form submissions must validate file scan status."""
        from app.services.form import _validate_file_scan_status

        questions = [{"id": "q1", "type": "file_upload", "label": "Doc"}]
        answers = {"q1": {"key": "forms/uploads/test/abc.pdf", "filename": "doc.pdf"}}

        with patch(
            "app.repositories.file_scan_repo.is_clean",
            new_callable=AsyncMock,
            return_value=False,
        ):
            with pytest.raises(ValueError, match="not yet cleared"):
                await _validate_file_scan_status(questions, answers)

    @pytest.mark.asyncio
    async def test_guest_file_upload_size_checked(self):
        """Guest form submissions must validate file sizes."""
        from app.services.form import _validate_file_sizes

        questions = [
            {"id": "q1", "type": "file_upload", "label": "Doc", "max_size_mb": 5}
        ]
        answers = {"q1": {"key": "forms/uploads/test/abc.pdf", "filename": "doc.pdf"}}

        with patch(
            "app.core.async_storage.get_file_size",
            new_callable=AsyncMock,
            return_value=10 * 1024 * 1024,
        ):
            with pytest.raises(ValueError, match="exceeds the maximum size"):
                await _validate_file_sizes(questions, answers)

    @pytest.mark.asyncio
    async def test_guest_submit_form_runs_file_validation(self, mock_pool, mock_conn):
        """submit_response for guest must call scan/size/magic validation."""
        from app.services.form import submit_response

        form_id = uuid.uuid4()
        form_row = {
            "id": form_id,
            "is_deleted": False,
            "allow_non_members": True,
            "sig_id": None,
            "is_closed": False,
            "deadline": None,
            "max_respondents": None,
            "is_schema_locked": True,
            "questions": '[{"id":"q1","type":"file_upload","label":"Doc"}]',
        }

        with (
            patch(f"{_SVC_FORM}.get_pool", return_value=mock_pool),
            patch(
                f"{_SVC_FORM}.form_repo.find_for_update",
                new_callable=AsyncMock,
                return_value=form_row,
            ),
            patch(
                f"{_SVC_FORM}.form_repo.insert_response",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(f"{_SVC_FORM}._validate_file_scan_status", new_callable=AsyncMock) as mock_scan,
            patch(f"{_SVC_FORM}._validate_file_sizes", new_callable=AsyncMock) as mock_sizes,
            patch(f"{_SVC_FORM}._validate_file_magic_bytes", new_callable=AsyncMock) as mock_magic,
        ):
            answers = {"q1": {"key": "forms/uploads/x/abc.pdf", "filename": "test.pdf"}}
            await submit_response(form_id, None, answers, is_guest=True)

            mock_scan.assert_awaited_once()
            mock_sizes.assert_awaited_once()
            mock_magic.assert_awaited_once()


# ---------------------------------------------------------------------------
# H-02: Form file uploads lack magic byte validation
# ---------------------------------------------------------------------------


class TestH02FormFileMagicBytes:
    @pytest.mark.asyncio
    async def test_magic_bytes_mismatch_rejected(self):
        """Form file upload with mismatched magic bytes should be rejected."""
        from app.services.form import _validate_file_magic_bytes

        questions = [{"id": "q1", "type": "file_upload", "label": "Doc"}]
        answers = {"q1": {"key": "forms/uploads/x/test.pdf", "filename": "test.pdf"}}

        with patch(
            "app.core.async_storage.read_file_header",
            new_callable=AsyncMock,
            return_value=b"NOT_A_PDF_CONTENT",
        ):
            with pytest.raises(ValueError, match="does not match its extension"):
                await _validate_file_magic_bytes(questions, answers)

    @pytest.mark.asyncio
    async def test_magic_bytes_match_accepted(self):
        """Form file upload with correct magic bytes should pass."""
        from app.services.form import _validate_file_magic_bytes

        questions = [{"id": "q1", "type": "file_upload", "label": "Doc"}]
        answers = {"q1": {"key": "forms/uploads/x/test.pdf", "filename": "test.pdf"}}

        with patch(
            "app.core.async_storage.read_file_header",
            new_callable=AsyncMock,
            return_value=b"%PDF-1.4 some content",
        ):
            await _validate_file_magic_bytes(questions, answers)

    @pytest.mark.asyncio
    async def test_magic_bytes_png_mismatch(self):
        """PNG extension with JPEG magic bytes should be rejected."""
        from app.services.form import _validate_file_magic_bytes

        questions = [{"id": "q1", "type": "file_upload", "label": "Image"}]
        answers = {"q1": {"key": "forms/uploads/x/test.png", "filename": "test.png"}}

        with patch(
            "app.core.async_storage.read_file_header",
            new_callable=AsyncMock,
            return_value=b"\xff\xd8\xff some content",
        ):
            with pytest.raises(ValueError, match="does not match its extension"):
                await _validate_file_magic_bytes(questions, answers)

    @pytest.mark.asyncio
    async def test_magic_bytes_storage_error(self):
        """File that can't be read from storage should raise ValueError."""
        from app.services.form import _validate_file_magic_bytes

        questions = [{"id": "q1", "type": "file_upload", "label": "Doc"}]
        answers = {"q1": {"key": "forms/uploads/x/test.pdf", "filename": "test.pdf"}}

        with patch(
            "app.core.async_storage.read_file_header",
            new_callable=AsyncMock,
            side_effect=Exception("S3 error"),
        ):
            with pytest.raises(ValueError, match="could not be read"):
                await _validate_file_magic_bytes(questions, answers)

    @pytest.mark.asyncio
    async def test_nonexistent_file_rejected(self):
        """Non-existent file in storage should be rejected."""
        from app.services.form import _validate_file_magic_bytes

        questions = [{"id": "q1", "type": "file_upload", "label": "Doc"}]
        answers = {"q1": {"key": "forms/uploads/x/ghost.pdf", "filename": "ghost.pdf"}}

        with patch(
            "app.core.async_storage.read_file_header",
            new_callable=AsyncMock,
            return_value=b"",
        ):
            with pytest.raises(ValueError, match="not found in storage"):
                await _validate_file_magic_bytes(questions, answers)

    @pytest.mark.asyncio
    async def test_non_file_upload_questions_skipped(self):
        """Non file_upload questions should be skipped without error."""
        from app.services.form import _validate_file_magic_bytes

        questions = [{"id": "q1", "type": "text", "label": "Name"}]
        answers = {"q1": "hello"}
        await _validate_file_magic_bytes(questions, answers)


# ---------------------------------------------------------------------------
# H-03: DM admin audit event silently swallowed
# ---------------------------------------------------------------------------


class TestH03DmAdminAuditLogging:
    @pytest.mark.asyncio
    async def test_audit_failure_logged(self, client):
        """DM admin audit failure should be logged, not silently swallowed."""
        conv_id = str(uuid.uuid4())

        try:
            _override_auth("SUPER_ADMIN")
            with (
                patch(
                    "app.api.v1.endpoints.dm.check_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    "app.core.event_bus.emit",
                    new_callable=AsyncMock,
                    side_effect=RuntimeError("event bus down"),
                ),
                patch(
                    "app.repositories.dm_repo.conversation_exists",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch(
                    "app.repositories.dm_repo.find_messages",
                    new_callable=AsyncMock,
                    return_value=([], 0),
                ),
                patch("app.api.v1.endpoints.dm.logger") as mock_logger,
            ):
                resp = await client.get(
                    f"/api/v1/dm/admin/conversations/{conv_id}/messages",
                )
                assert resp.status_code == 200
                mock_logger.error.assert_called_once()
                assert "Failed to log DM admin access" in mock_logger.error.call_args[0][0]
        finally:
            _clear_overrides()


# ---------------------------------------------------------------------------
# H-04: SIG member removal uses hard DELETE
# ---------------------------------------------------------------------------


class TestH04SigMemberSoftDelete:
    @pytest.mark.asyncio
    async def test_delete_member_uses_soft_delete(self):
        """delete_member (used by service layer) should soft-delete, not hard DELETE."""
        from app.repositories import sig_repo

        sig_id = uuid.uuid4()
        user_id = uuid.uuid4()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        result = await sig_repo.delete_member(sig_id, user_id, mock_conn)
        assert result is True

        sql = mock_conn.execute.call_args_list[0][0][0]
        assert "UPDATE sig_members SET is_deleted = true" in sql
        assert "DELETE" not in sql

    @pytest.mark.asyncio
    async def test_delete_member_not_found(self):
        """delete_member returns False when member not found."""
        from app.repositories import sig_repo

        sig_id = uuid.uuid4()
        user_id = uuid.uuid4()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 0")

        result = await sig_repo.delete_member(sig_id, user_id, mock_conn)
        assert result is False

    @pytest.mark.asyncio
    async def test_remove_member_also_soft_deletes(self):
        """remove_member (standalone) should also use soft delete."""
        from app.repositories import sig_repo

        sig_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")
        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=tx)

        mock_pool = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = cm

        with patch("app.repositories.sig_repo.get_pool", return_value=mock_pool):
            result = await sig_repo.remove_member(sig_id, user_id)
            assert result is True

            sql = mock_conn.execute.call_args_list[0][0][0]
            assert "UPDATE sig_members SET is_deleted = true" in sql
            assert "DELETE" not in sql


# ---------------------------------------------------------------------------
# H-05: Bulk role change audit log lacks per-user detail
# ---------------------------------------------------------------------------


class TestH05BulkRoleAuditDetail:
    @pytest.mark.asyncio
    async def test_bulk_role_change_logs_user_ids(self, client):
        """Bulk role change audit log should include changed user IDs."""
        uid1, uid2 = uuid.uuid4(), uuid.uuid4()

        try:
            _override_auth("SUPER_ADMIN")
            with (
                patch(
                    "app.services.user.bulk_change_role",
                    new_callable=AsyncMock,
                    return_value=(2, [uid1, uid2]),
                ),
                patch(
                    "app.core.event_bus.emit",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.services.auth.revoke_user_sessions",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.services.audit.log_action",
                    new_callable=AsyncMock,
                ) as mock_log,
            ):
                resp = await client.put(
                    "/api/v1/users/bulk-role",
                    json={"user_ids": [str(uid1), str(uid2)], "role": "MEMBER"},
                )
                assert resp.status_code == 200

                mock_log.assert_awaited_once()
                call_kwargs = mock_log.call_args[1]
                target_id = call_kwargs["target_id"]
                assert str(uid1) in target_id
                assert str(uid2) in target_id
                assert "role=MEMBER" in target_id
                assert "count=2" in target_id
        finally:
            _clear_overrides()
