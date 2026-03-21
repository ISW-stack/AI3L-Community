"""Tests for session 3 audit fixes: L-17, L-18, L-19, L-20, L-24, L-46, M-36."""

import asyncio
import inspect
import types
import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.errors import AppError

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_pool_with_conn(mock_conn: AsyncMock) -> MagicMock:
    """Build a mock pool whose ``acquire()`` yields *mock_conn*."""
    pool = MagicMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool


def _make_conn_with_transaction() -> AsyncMock:
    """Return an AsyncMock connection with a working transaction() context manager.

    asyncpg ``conn.transaction()`` is a synchronous call returning an async
    context manager, so we use MagicMock for the method and wire up
    ``__aenter__`` / ``__aexit__`` on the returned object.
    """
    conn = AsyncMock()
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)
    return conn


def _fake_album(album_id: str, created_by: str, **overrides: object) -> dict:
    """Minimal album dict with all fields needed by to_album_response."""
    base: dict = {
        "id": uuid.UUID(album_id),
        "created_by": uuid.UUID(created_by),
        "title": "Album",
        "description": None,
        "cover_photo_url": None,
        "is_archived": False,
        "photo_count": 0,
        "member_count": 0,
        "created_by_name": "Test",
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    base.update(overrides)
    return base


# ===========================================================================
# L-17: Album update_album -- permission check inside transaction
# ===========================================================================


class TestL17UpdateAlbumTransaction:
    """L-17: update_album must do permission check + update inside one transaction."""

    @pytest.mark.asyncio
    async def test_authorized_update_within_transaction(self) -> None:
        """Find + permission check + update must use the same conn inside a txn."""
        conn = _make_conn_with_transaction()
        pool = _mock_pool_with_conn(conn)

        album_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        fake = _fake_album(album_id, user_id)
        fake_updated = {**fake, "title": "New"}

        with (
            patch("app.services.album.get_pool", return_value=pool),
            patch("app.services.album.album_repo") as mock_repo,
            patch("app.services.album.to_album_response", return_value={"id": album_id}),
        ):
            mock_repo.find_album_by_id = AsyncMock(return_value=fake)
            mock_repo.find_member = AsyncMock(return_value=None)
            mock_repo.update_album = AsyncMock(return_value=fake_updated)

            from app.services.album import update_album

            await update_album(album_id, user_id, "MEMBER", title="New")

        mock_repo.find_album_by_id.assert_awaited_once_with(conn, uuid.UUID(album_id))
        mock_repo.update_album.assert_awaited_once_with(conn, uuid.UUID(album_id), title="New")
        conn.transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_unauthorized_raises_inside_transaction(self) -> None:
        """Non-owner, non-admin caller must get 403 inside the transaction."""
        conn = _make_conn_with_transaction()
        pool = _mock_pool_with_conn(conn)

        album_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        other_id = str(uuid.uuid4())

        fake = _fake_album(album_id, owner_id)

        with (
            patch("app.services.album.get_pool", return_value=pool),
            patch("app.services.album.album_repo") as mock_repo,
        ):
            mock_repo.find_album_by_id = AsyncMock(return_value=fake)
            mock_repo.find_member = AsyncMock(return_value=None)

            from app.services.album import update_album

            with pytest.raises(AppError) as exc_info:
                await update_album(album_id, other_id, "MEMBER", title="X")

            assert exc_info.value.status_code == 403

        mock_repo.find_album_by_id.assert_awaited_once_with(conn, uuid.UUID(album_id))
        conn.transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_album_admin_is_authorized(self) -> None:
        """An album-level ADMIN member should be authorized to update."""
        conn = _make_conn_with_transaction()
        pool = _mock_pool_with_conn(conn)

        album_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        admin_id = str(uuid.uuid4())

        fake = _fake_album(album_id, owner_id)

        with (
            patch("app.services.album.get_pool", return_value=pool),
            patch("app.services.album.album_repo") as mock_repo,
            patch("app.services.album.to_album_response", return_value={"id": album_id}),
        ):
            mock_repo.find_album_by_id = AsyncMock(return_value=fake)
            mock_repo.find_member = AsyncMock(return_value={"role": "ADMIN", "status": "ACCEPTED"})
            mock_repo.update_album = AsyncMock(return_value={**fake, "title": "New"})

            from app.services.album import update_album

            await update_album(album_id, admin_id, "MEMBER", title="New")

        mock_repo.update_album.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_site_admin_is_authorized(self) -> None:
        """A site SUPER_ADMIN should be authorized even if not album member."""
        conn = _make_conn_with_transaction()
        pool = _mock_pool_with_conn(conn)

        album_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        admin_id = str(uuid.uuid4())

        fake = _fake_album(album_id, owner_id)

        with (
            patch("app.services.album.get_pool", return_value=pool),
            patch("app.services.album.album_repo") as mock_repo,
            patch("app.services.album.to_album_response", return_value={"id": album_id}),
        ):
            mock_repo.find_album_by_id = AsyncMock(return_value=fake)
            mock_repo.find_member = AsyncMock(return_value=None)
            mock_repo.update_album = AsyncMock(return_value={**fake, "title": "New"})

            from app.services.album import update_album

            await update_album(album_id, admin_id, "SUPER_ADMIN", title="New")

        mock_repo.update_album.assert_awaited_once()


# ===========================================================================
# L-18: Album approve_member validates PENDING status
# ===========================================================================


class TestL18ApproveMemberPendingValidation:
    """L-18: approve_member must pass required_current_status='PENDING'."""

    @pytest.mark.asyncio
    async def test_approve_passes_required_current_status(self) -> None:
        conn = _make_conn_with_transaction()
        pool = _mock_pool_with_conn(conn)

        album_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        member_id = str(uuid.uuid4())

        fake = _fake_album(album_id, user_id)

        with (
            patch("app.services.album.get_pool", return_value=pool),
            patch("app.services.album.album_repo") as mock_repo,
        ):
            mock_repo.find_album_by_id = AsyncMock(return_value=fake)
            mock_repo.find_member = AsyncMock(return_value=None)
            mock_repo.update_member_status = AsyncMock(return_value=True)

            from app.services.album import approve_member

            result = await approve_member(album_id, user_id, member_id, "SUPER_ADMIN")

        assert result is True
        mock_repo.update_member_status.assert_awaited_once_with(
            conn,
            uuid.UUID(member_id),
            "ACCEPTED",
            album_id=uuid.UUID(album_id),
            required_current_status="PENDING",
        )

    @pytest.mark.asyncio
    async def test_approve_raises_when_no_pending_member(self) -> None:
        conn = _make_conn_with_transaction()
        pool = _mock_pool_with_conn(conn)

        album_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        member_id = str(uuid.uuid4())

        fake = _fake_album(album_id, user_id)

        with (
            patch("app.services.album.get_pool", return_value=pool),
            patch("app.services.album.album_repo") as mock_repo,
        ):
            mock_repo.find_album_by_id = AsyncMock(return_value=fake)
            mock_repo.find_member = AsyncMock(return_value=None)
            mock_repo.update_member_status = AsyncMock(return_value=False)

            from app.services.album import approve_member

            with pytest.raises(AppError) as exc_info:
                await approve_member(album_id, user_id, member_id, "SUPER_ADMIN")

            assert exc_info.value.status_code == 404
            assert "Pending member not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_approve_already_accepted_member_fails(self) -> None:
        """Member already ACCEPTED -> update_member_status returns False -> 404."""
        conn = _make_conn_with_transaction()
        pool = _mock_pool_with_conn(conn)

        album_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        member_id = str(uuid.uuid4())

        fake = _fake_album(album_id, user_id)

        with (
            patch("app.services.album.get_pool", return_value=pool),
            patch("app.services.album.album_repo") as mock_repo,
        ):
            mock_repo.find_album_by_id = AsyncMock(return_value=fake)
            mock_repo.find_member = AsyncMock(return_value=None)
            mock_repo.update_member_status = AsyncMock(return_value=False)

            from app.services.album import approve_member

            with pytest.raises(AppError) as exc_info:
                await approve_member(album_id, user_id, member_id, "SUPER_ADMIN")

            assert exc_info.value.status_code == 404


# ===========================================================================
# L-19: Form create -- active count check is atomic with creation
# ===========================================================================


class TestL19FormCreateAtomicCount:
    """L-19: create_form count + insert must be in the same transaction."""

    @pytest.mark.asyncio
    async def test_sig_form_count_and_insert_in_same_transaction(self) -> None:
        conn = _make_conn_with_transaction()
        pool = _mock_pool_with_conn(conn)
        sig_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        with (
            patch("app.services.form.get_pool", return_value=pool),
            patch("app.services.form.form_repo") as mock_repo,
            patch("app.services.form.row_to_form", return_value={"id": "x"}),
        ):
            mock_repo.count_active_in_conn = AsyncMock(return_value=0)
            mock_repo.insert_in_conn = AsyncMock(return_value={"id": uuid.uuid4()})

            from app.services.form import create_form

            await create_form(
                sig_id=sig_id,
                user_id=user_id,
                title="T",
                description=None,
                banner_url=None,
                deadline=None,
                max_respondents=None,
                questions=[{"id": "q1", "type": "text", "label": "Q"}],
            )

        mock_repo.count_active_in_conn.assert_awaited_once_with(conn, uuid.UUID(sig_id))
        mock_repo.insert_in_conn.assert_awaited_once()
        assert mock_repo.insert_in_conn.call_args[0][0] is conn
        conn.transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_standalone_form_count_and_insert_in_same_transaction(self) -> None:
        conn = _make_conn_with_transaction()
        pool = _mock_pool_with_conn(conn)
        user_id = str(uuid.uuid4())

        with (
            patch("app.services.form.get_pool", return_value=pool),
            patch("app.services.form.form_repo") as mock_repo,
            patch("app.services.form.row_to_form", return_value={"id": "x"}),
        ):
            mock_repo.count_active_standalone_by_user = AsyncMock(return_value=0)
            mock_repo.insert_in_conn = AsyncMock(return_value={"id": uuid.uuid4()})

            from app.services.form import create_form

            await create_form(
                sig_id=None,
                user_id=user_id,
                title="T",
                description=None,
                banner_url=None,
                deadline=None,
                max_respondents=None,
                questions=[{"id": "q1", "type": "text", "label": "Q"}],
            )

        mock_repo.count_active_standalone_by_user.assert_awaited_once_with(
            conn, uuid.UUID(user_id)
        )
        mock_repo.insert_in_conn.assert_awaited_once()
        assert mock_repo.insert_in_conn.call_args[0][0] is conn
        conn.transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_sig_form_limit_reached_raises(self) -> None:
        conn = _make_conn_with_transaction()
        pool = _mock_pool_with_conn(conn)

        from app.core.constants import MAX_ACTIVE_FORMS_PER_SIG

        with (
            patch("app.services.form.get_pool", return_value=pool),
            patch("app.services.form.form_repo") as mock_repo,
            patch("app.services.form.row_to_form", return_value={}),
        ):
            mock_repo.count_active_in_conn = AsyncMock(return_value=MAX_ACTIVE_FORMS_PER_SIG)

            from app.services.form import create_form

            with pytest.raises(ValueError, match="Maximum active forms"):
                await create_form(
                    sig_id=str(uuid.uuid4()),
                    user_id=str(uuid.uuid4()),
                    title="T",
                    description=None,
                    banner_url=None,
                    deadline=None,
                    max_respondents=None,
                    questions=[{"id": "q1", "type": "text", "label": "Q"}],
                )

            mock_repo.insert_in_conn.assert_not_called()


# ===========================================================================
# L-20: Post create -- SIG membership check in same transaction as insert
# ===========================================================================


class TestL20PostCreateSigMembershipAtomic:
    """L-20: SIG membership check and insert must be in the same txn."""

    @pytest.mark.asyncio
    async def test_sig_membership_and_insert_same_transaction(self) -> None:
        conn = _make_conn_with_transaction()
        pool = _mock_pool_with_conn(conn)
        sig_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        with (
            patch("app.services.post.get_pool", return_value=pool),
            patch("app.services.post.post_repo") as mock_post_repo,
            patch("app.services.post._atomic_check_and_increment_post_limit", new_callable=AsyncMock, return_value=True),
            patch("app.services.post.emit", new_callable=AsyncMock),
            patch("app.services.post.async_row_to_post", new_callable=AsyncMock, return_value={"id": "x"}),
            patch("app.repositories.sig_repo.get_member_role_in_conn", new_callable=AsyncMock, return_value="MEMBER") as mock_sig,
        ):
            mock_post_repo.insert_in_conn = AsyncMock(return_value={"id": uuid.uuid4()})

            from app.services.post import create_post

            await create_post(user_id=user_id, title="T", content="<p>B</p>", sig_id=sig_id)

        mock_sig.assert_awaited_once_with(uuid.UUID(sig_id), uuid.UUID(user_id), conn)
        assert mock_post_repo.insert_in_conn.call_args[0][0] is conn
        conn.transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_member_rejected_inside_transaction(self) -> None:
        conn = _make_conn_with_transaction()
        pool = _mock_pool_with_conn(conn)
        sig_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        with (
            patch("app.services.post.get_pool", return_value=pool),
            patch("app.services.post.post_repo") as mock_post_repo,
            patch("app.services.post._atomic_check_and_increment_post_limit", new_callable=AsyncMock, return_value=True),
            patch("app.services.post._rollback_daily_post_count", new_callable=AsyncMock),
            patch("app.services.post.async_row_to_post", new_callable=AsyncMock),
            patch("app.repositories.sig_repo.get_member_role_in_conn", new_callable=AsyncMock, return_value=None),
        ):
            from app.services.post import create_post

            with pytest.raises(PermissionError, match="must be a member"):
                await create_post(user_id=user_id, title="T", content="<p>B</p>", sig_id=sig_id)

            mock_post_repo.insert_in_conn.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_sig_post_skips_membership_check(self) -> None:
        """Posts without a SIG should not do any membership check."""
        conn = _make_conn_with_transaction()
        pool = _mock_pool_with_conn(conn)
        user_id = str(uuid.uuid4())

        with (
            patch("app.services.post.get_pool", return_value=pool),
            patch("app.services.post.post_repo") as mock_post_repo,
            patch("app.services.post._atomic_check_and_increment_post_limit", new_callable=AsyncMock, return_value=True),
            patch("app.services.post.emit", new_callable=AsyncMock),
            patch("app.services.post.async_row_to_post", new_callable=AsyncMock, return_value={"id": "p1"}),
        ):
            mock_post_repo.insert_in_conn = AsyncMock(return_value=MagicMock())

            from app.services.post import create_post

            await create_post(user_id=user_id, title="T", content="<p>B</p>", sig_id=None)

        mock_post_repo.insert_in_conn.assert_awaited_once()


# ===========================================================================
# L-24: audit_repo.find_many accepts date type params (not just str)
# ===========================================================================


class TestL24AuditRepoDateParams:
    """L-24: audit_repo.find_many date_from/date_to must accept datetime.date."""

    def test_find_many_signature_accepts_date_type(self) -> None:
        from app.repositories.audit_repo import find_many

        sig = inspect.signature(find_many)
        for pname in ("date_from", "date_to"):
            annotation = sig.parameters[pname].annotation
            if isinstance(annotation, types.UnionType):
                assert date in annotation.__args__
            else:
                assert annotation is not str

    def test_endpoint_uses_date_type_not_str(self) -> None:
        """The audit logs endpoint should declare date params as DateType."""
        from app.api.v1.endpoints.users import get_audit_logs

        sig = inspect.signature(get_audit_logs)
        for pname in ("date_from", "date_to"):
            annotation = sig.parameters[pname].annotation
            if isinstance(annotation, types.UnionType):
                assert date in annotation.__args__
            else:
                assert annotation is not str

    @pytest.mark.asyncio
    async def test_find_many_builds_query_with_date_objects(self) -> None:
        """Verify find_many can be called with date objects (SQL ::timestamptz handles it)."""
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=0)
        conn.fetch = AsyncMock(return_value=[])
        pool = _mock_pool_with_conn(conn)

        with patch("app.repositories.audit_repo.get_pool", return_value=pool):
            from app.repositories.audit_repo import find_many

            rows, total = await find_many(
                page=1,
                page_size=10,
                date_from=date(2026, 1, 1),
                date_to=date(2026, 3, 1),
            )

        assert total == 0
        assert rows == []
        params = conn.fetchval.call_args[0][1:]
        assert date(2026, 1, 1) in params
        assert date(2026, 3, 1) in params


# ===========================================================================
# L-46: Album cover -- MinIO cleanup on DB failure
# ===========================================================================


class TestL46AlbumCoverMinIOCleanup:
    """L-46: upload_cover must clean up MinIO file if DB update fails."""

    @pytest.mark.asyncio
    async def test_db_failure_triggers_minio_cleanup(self) -> None:
        """DB transaction fails in Phase 3 -> MinIO file deleted + AppError 500."""
        album_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        fake = _fake_album(album_id, user_id)

        conn1 = _make_conn_with_transaction()
        conn1.fetchrow = AsyncMock(return_value={"storage_used_bytes": 0})

        conn3 = _make_conn_with_transaction()
        conn3_tx = conn3.transaction.return_value
        conn3_tx.__aenter__ = AsyncMock(side_effect=RuntimeError("DB exploded"))

        pool = MagicMock()
        call_count = 0

        def _acquire():
            nonlocal call_count
            call_count += 1
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=conn1 if call_count == 1 else conn3)
            ctx.__aexit__ = AsyncMock(return_value=False)
            return ctx

        pool.acquire = _acquire

        mock_upload = AsyncMock()
        mock_delete = AsyncMock()

        with (
            patch("app.services.album.get_pool", return_value=pool),
            patch("app.services.album.album_repo") as mock_repo,
            patch("app.services.album.settings") as mock_settings,
            patch("app.core.async_storage.upload_file", mock_upload),
            patch("app.core.async_storage.delete_file", mock_delete),
        ):
            mock_repo.find_album_by_id = AsyncMock(return_value=fake)
            mock_repo.find_member = AsyncMock(return_value=None)
            mock_settings.MAX_USER_STORAGE_BYTES = 10 * 1024 * 1024 * 1024

            from app.services.album import upload_cover

            with pytest.raises(AppError) as exc_info:
                await upload_cover(
                    album_id=album_id,
                    user_id=user_id,
                    user_role="SUPER_ADMIN",
                    file_data=b"\x89PNG\r\n\x1a\n" + b"\x00" * 100,
                    filename="cover.png",
                    content_type="image/png",
                )

            assert exc_info.value.status_code == 500

        mock_upload.assert_awaited_once()
        mock_delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_successful_upload_no_orphan_cleanup(self) -> None:
        """When everything succeeds, no orphan cleanup delete should happen."""
        album_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        fake = _fake_album(album_id, user_id)

        conn1 = _make_conn_with_transaction()
        conn1.fetchrow = AsyncMock(return_value={"storage_used_bytes": 0})

        conn3 = _make_conn_with_transaction()
        conn3.execute = AsyncMock()

        pool = MagicMock()
        call_count = 0

        def _acquire():
            nonlocal call_count
            call_count += 1
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=conn1 if call_count <= 1 else conn3)
            ctx.__aexit__ = AsyncMock(return_value=False)
            return ctx

        pool.acquire = _acquire

        mock_upload = AsyncMock()
        mock_delete = AsyncMock()

        with (
            patch("app.services.album.get_pool", return_value=pool),
            patch("app.services.album.album_repo") as mock_repo,
            patch("app.services.album.settings") as mock_settings,
            patch("app.services.album.to_album_response", return_value={"id": album_id}),
            patch("app.core.async_storage.upload_file", mock_upload),
            patch("app.core.async_storage.delete_file", mock_delete),
        ):
            mock_repo.find_album_by_id = AsyncMock(return_value=fake)
            mock_repo.find_member = AsyncMock(return_value=None)
            mock_repo.set_cover_photo = AsyncMock()
            mock_settings.MAX_USER_STORAGE_BYTES = 10 * 1024 * 1024 * 1024

            from app.services.album import upload_cover

            result = await upload_cover(
                album_id=album_id,
                user_id=user_id,
                user_role="SUPER_ADMIN",
                file_data=b"\x89PNG\r\n\x1a\n" + b"\x00" * 100,
                filename="cover.png",
                content_type="image/png",
            )

        mock_upload.assert_awaited_once()
        mock_delete.assert_not_awaited()
        assert result == {"id": album_id}

    @pytest.mark.asyncio
    async def test_db_failure_cleanup_also_fails_still_raises(self) -> None:
        """Even if MinIO cleanup fails after DB failure, AppError is still raised."""
        album_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        fake = _fake_album(album_id, user_id)

        conn1 = _make_conn_with_transaction()
        conn1.fetchrow = AsyncMock(return_value={"storage_used_bytes": 0})

        conn3 = _make_conn_with_transaction()
        conn3_tx = conn3.transaction.return_value
        conn3_tx.__aenter__ = AsyncMock(side_effect=RuntimeError("DB exploded"))

        pool = MagicMock()
        call_count = 0

        def _acquire():
            nonlocal call_count
            call_count += 1
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=conn1 if call_count == 1 else conn3)
            ctx.__aexit__ = AsyncMock(return_value=False)
            return ctx

        pool.acquire = _acquire

        mock_upload = AsyncMock()
        mock_delete = AsyncMock(side_effect=RuntimeError("MinIO also failed"))

        with (
            patch("app.services.album.get_pool", return_value=pool),
            patch("app.services.album.album_repo") as mock_repo,
            patch("app.services.album.settings") as mock_settings,
            patch("app.core.async_storage.upload_file", mock_upload),
            patch("app.core.async_storage.delete_file", mock_delete),
        ):
            mock_repo.find_album_by_id = AsyncMock(return_value=fake)
            mock_repo.find_member = AsyncMock(return_value=None)
            mock_settings.MAX_USER_STORAGE_BYTES = 10 * 1024 * 1024 * 1024

            from app.services.album import upload_cover

            with pytest.raises(AppError) as exc_info:
                await upload_cover(
                    album_id=album_id,
                    user_id=user_id,
                    user_role="SUPER_ADMIN",
                    file_data=b"\x89PNG\r\n\x1a\n" + b"\x00" * 100,
                    filename="cover.png",
                    content_type="image/png",
                )

            assert exc_info.value.status_code == 500


# ===========================================================================
# M-36: Admin user list -- presigned URLs via asyncio.gather (N+1 fix)
# ===========================================================================


class TestM36PresignedURLGather:
    """M-36: Admin user list must use asyncio.gather for presigned URLs."""

    def test_get_all_users_uses_asyncio_gather(self) -> None:
        """Verify that the endpoint source contains asyncio.gather."""
        from app.api.v1.endpoints.users import get_all_users

        source = inspect.getsource(get_all_users)
        assert "asyncio.gather" in source, (
            "get_all_users should use asyncio.gather for concurrent "
            "presigned URL generation (N+1 fix)"
        )

    def test_gather_wraps_all_user_conversions(self) -> None:
        """The gather call should wrap async_user_to_response for each user."""
        from app.api.v1.endpoints.users import get_all_users

        source = inspect.getsource(get_all_users)
        assert "async_user_to_response(u)" in source
        assert "for u in users" in source

    @pytest.mark.asyncio
    async def test_multiple_users_processed_concurrently(self) -> None:
        """async_user_to_response must be called for each user via gather."""
        from app.schemas.user import UserResponse

        user1 = {"id": uuid.uuid4(), "username": "alice", "display_name": "Alice", "role": "MEMBER", "avatar_url": "a.png"}
        user2 = {"id": uuid.uuid4(), "username": "bob", "display_name": "Bob", "role": "MEMBER", "avatar_url": "b.png"}

        fake_resp = UserResponse(
            id=str(uuid.uuid4()), username="x", display_name="X", role="MEMBER", avatar_url=None,
        )

        with (
            patch("app.api.v1.endpoints.users.list_users", new_callable=AsyncMock, return_value=([user1, user2], 2)),
            patch("app.api.v1.endpoints.users.async_user_to_response", new_callable=AsyncMock, return_value=fake_resp) as mock_convert,
        ):
            from app.api.v1.endpoints.users import get_all_users

            current_user = {"sub": str(uuid.uuid4()), "role": "SUPER_ADMIN"}
            await get_all_users(page=1, page_size=50, search=None, current_user=current_user)

        assert mock_convert.await_count == 2

    def test_endpoint_imports_asyncio(self) -> None:
        """The users endpoint module must import asyncio for gather."""
        import app.api.v1.endpoints.users as users_mod

        assert hasattr(users_mod, "asyncio")
