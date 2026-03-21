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
    """Build a mock pool whose `acquire()` yields *mock_conn*."""
    pool = MagicMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool


def _make_conn_with_transaction() -> AsyncMock:
    """Return an AsyncMock connection with a working transaction() context manager."""
    conn = AsyncMock()
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)
    return conn


# ===========================================================================
# L-17: Album update_album — permission check inside transaction
# ===========================================================================


class TestL17UpdateAlbumTransaction:
    """L-17: update_album must do permission check + update inside one transaction."""

    @pytest.mark.asyncio
    async def test_authorized_update_within_transaction(self) -> None:
        conn = _make_conn_with_transaction()
        pool = _mock_pool_with_conn(conn)

        album_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        fake_album = {
            "id": uuid.UUID(album_id), "created_by": uuid.UUID(user_id),
            "title": "Old", "description": "Old desc", "cover_photo_url": None,
            "created_at": _NOW, "updated_at": _NOW,
            "is_archived": False, "photo_count": 0, "member_count": 0,
        }
        fake_updated = {**fake_album, "title": "New"}

        with (
            patch("app.services.album.get_pool", return_value=pool),
            patch("app.services.album.album_repo") as mock_repo,
            patch("app.services.album.to_album_response", return_value={"id": album_id}),
        ):
            mock_repo.find_album_by_id = AsyncMock(return_value=fake_album)
            mock_repo.find_member = AsyncMock(return_value=None)
            mock_repo.update_album = AsyncMock(return_value=fake_updated)

            from app.services.album import update_album

            await update_album(album_id, user_id, "MEMBER", title="New")

        mock_repo.find_album_by_id.assert_awaited_once_with(conn, uuid.UUID(album_id))
        mock_repo.update_album.assert_awaited_once_with(conn, uuid.UUID(album_id), title="New")
        conn.transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_unauthorized_raises_inside_transaction(self) -> None:
        conn = _make_conn_with_transaction()
        pool = _mock_pool_with_conn(conn)

        album_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        other_id = str(uuid.uuid4())

        fake_album = {
            "id": uuid.UUID(album_id), "created_by": uuid.UUID(owner_id),
            "title": "T", "description": None,
        }

        with (
            patch("app.services.album.get_pool", return_value=pool),
            patch("app.services.album.album_repo") as mock_repo,
        ):
            mock_repo.find_album_by_id = AsyncMock(return_value=fake_album)
            mock_repo.find_member = AsyncMock(return_value=None)

            from app.services.album import update_album

            with pytest.raises(AppError) as exc_info:
                await update_album(album_id, other_id, "MEMBER", title="X")

            assert exc_info.value.status_code == 403

        conn.transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_album_admin_is_authorized(self) -> None:
        conn = _make_conn_with_transaction()
        pool = _mock_pool_with_conn(conn)

        album_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        admin_id = str(uuid.uuid4())

        fake_album = {
            "id": uuid.UUID(album_id), "created_by": uuid.UUID(owner_id),
            "title": "T", "description": None, "cover_photo_url": None,
            "created_at": _NOW, "updated_at": _NOW,
            "is_archived": False, "photo_count": 0, "member_count": 0,
        }

        with (
            patch("app.services.album.get_pool", return_value=pool),
            patch("app.services.album.album_repo") as mock_repo,
            patch("app.services.album.to_album_response", return_value={"id": album_id}),
        ):
            mock_repo.find_album_by_id = AsyncMock(return_value=fake_album)
            mock_repo.find_member = AsyncMock(return_value={"role": "ADMIN", "status": "ACCEPTED"})
            mock_repo.update_album = AsyncMock(return_value={**fake_album, "title": "New"})

            from app.services.album import update_album

            await update_album(album_id, admin_id, "MEMBER", title="New")

        mock_repo.update_album.assert_awaited_once()


# ===========================================================================
# L-18: Album approve_member validates PENDING status
# ===========================================================================


class TestL18ApproveMemberPendingValidation:

    @pytest.mark.asyncio
    async def test_approve_passes_required_current_status(self) -> None:
        conn = _make_conn_with_transaction()
        pool = _mock_pool_with_conn(conn)

        album_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        member_id = str(uuid.uuid4())

        with (
            patch("app.services.album.get_pool", return_value=pool),
            patch("app.services.album.album_repo") as mock_repo,
        ):
            mock_repo.find_album_by_id = AsyncMock(
                return_value={"id": uuid.UUID(album_id), "created_by": uuid.UUID(user_id)}
            )
            mock_repo.find_member = AsyncMock(return_value=None)
            mock_repo.update_member_status = AsyncMock(return_value=True)

            from app.services.album import approve_member

            await approve_member(album_id, user_id, member_id, "SUPER_ADMIN")

        mock_repo.update_member_status.assert_awaited_once_with(
            conn, uuid.UUID(member_id), "ACCEPTED",
            album_id=uuid.UUID(album_id), required_current_status="PENDING",
        )

    @pytest.mark.asyncio
    async def test_approve_raises_when_no_pending_member(self) -> None:
        conn = _make_conn_with_transaction()
        pool = _mock_pool_with_conn(conn)

        album_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        member_id = str(uuid.uuid4())

        with (
            patch("app.services.album.get_pool", return_value=pool),
            patch("app.services.album.album_repo") as mock_repo,
        ):
            mock_repo.find_album_by_id = AsyncMock(
                return_value={"id": uuid.UUID(album_id), "created_by": uuid.UUID(user_id)}
            )
            mock_repo.find_member = AsyncMock(return_value=None)
            mock_repo.update_member_status = AsyncMock(return_value=False)

            from app.services.album import approve_member

            with pytest.raises(AppError) as exc_info:
                await approve_member(album_id, user_id, member_id, "SUPER_ADMIN")
            assert exc_info.value.status_code == 404


# ===========================================================================
# L-19: Form create — active count check is atomic with creation
# ===========================================================================


class TestL19FormCreateAtomicCount:

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
                sig_id=sig_id, user_id=user_id, title="T",
                description=None, banner_url=None, deadline=None,
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
                sig_id=None, user_id=user_id, title="T",
                description=None, banner_url=None, deadline=None,
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
                    sig_id=str(uuid.uuid4()), user_id=str(uuid.uuid4()), title="T",
                    description=None, banner_url=None, deadline=None,
                    max_respondents=None,
                    questions=[{"id": "q1", "type": "text", "label": "Q"}],
                )


# ===========================================================================
# L-20: Post create — SIG membership check in same transaction as insert
# ===========================================================================


class TestL20PostCreateSigMembershipAtomic:

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
            patch("app.services.post.post_repo"),
            patch("app.services.post._atomic_check_and_increment_post_limit", new_callable=AsyncMock, return_value=True),
            patch("app.services.post._rollback_daily_post_count", new_callable=AsyncMock),
            patch("app.services.post.async_row_to_post", new_callable=AsyncMock),
            patch("app.repositories.sig_repo.get_member_role_in_conn", new_callable=AsyncMock, return_value=None),
        ):
            from app.services.post import create_post

            with pytest.raises(PermissionError, match="must be a member"):
                await create_post(user_id=user_id, title="T", content="<p>B</p>", sig_id=sig_id)


# ===========================================================================
# L-24: audit_repo.find_many accepts date type params
# ===========================================================================


class TestL24AuditRepoDateParams:

    def test_find_many_signature_accepts_date_type(self) -> None:
        from app.repositories.audit_repo import find_many

        sig = inspect.signature(find_many)
        for pname in ("date_from", "date_to"):
            annotation = sig.parameters[pname].annotation
            if isinstance(annotation, types.UnionType):
                assert date in annotation.__args__
            else:
                assert annotation is not str

    @pytest.mark.asyncio
    async def test_find_many_builds_query_with_date_objects(self) -> None:
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=0)
        conn.fetch = AsyncMock(return_value=[])
        pool = _mock_pool_with_conn(conn)

        with patch("app.repositories.audit_repo.get_pool", return_value=pool):
            from app.repositories.audit_repo import find_many

            rows, total = await find_many(
                page=1, page_size=10,
                date_from=date(2026, 1, 1), date_to=date(2026, 3, 1),
            )

        assert total == 0
        params = conn.fetchval.call_args[0][1:]
        assert date(2026, 1, 1) in params
        assert date(2026, 3, 1) in params


# ===========================================================================
# L-46: Album cover — MinIO cleanup on DB failure
# ===========================================================================


class TestL46AlbumCoverMinIOCleanup:

    @pytest.mark.asyncio
    async def test_db_failure_triggers_minio_cleanup(self) -> None:
        album_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        fake_album = {"id": uuid.UUID(album_id), "created_by": uuid.UUID(user_id), "cover_photo_url": None}

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
            mock_repo.find_album_by_id = AsyncMock(return_value=fake_album)
            mock_repo.find_member = AsyncMock(return_value=None)
            mock_settings.MAX_USER_STORAGE_BYTES = 10 * 1024 * 1024 * 1024

            from app.services.album import upload_cover

            with pytest.raises(AppError) as exc_info:
                await upload_cover(
                    album_id=album_id, user_id=user_id, user_role="SUPER_ADMIN",
                    file_data=b"\x89PNG\r\n\x1a\n" + b"\x00" * 100,
                    filename="cover.png", content_type="image/png",
                )
            assert exc_info.value.status_code == 500

        mock_upload.assert_awaited_once()
        mock_delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_successful_upload_no_orphan_cleanup(self) -> None:
        album_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        fake_album = {"id": uuid.UUID(album_id), "created_by": uuid.UUID(user_id), "cover_photo_url": None}

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

        with (
            patch("app.services.album.get_pool", return_value=pool),
            patch("app.services.album.album_repo") as mock_repo,
            patch("app.services.album.settings") as mock_settings,
            patch("app.services.album.to_album_response", return_value={"id": album_id}),
            patch("app.core.async_storage.upload_file", mock_upload),
            patch("app.core.async_storage.delete_file", AsyncMock()),
        ):
            mock_repo.find_album_by_id = AsyncMock(return_value=fake_album)
            mock_repo.find_member = AsyncMock(return_value=None)
            mock_repo.set_cover_photo = AsyncMock()
            mock_settings.MAX_USER_STORAGE_BYTES = 10 * 1024 * 1024 * 1024

            from app.services.album import upload_cover

            await upload_cover(
                album_id=album_id, user_id=user_id, user_role="SUPER_ADMIN",
                file_data=b"\x89PNG\r\n\x1a\n" + b"\x00" * 100,
                filename="cover.png", content_type="image/png",
            )

        mock_upload.assert_awaited_once()


# ===========================================================================
# M-36: Admin user list — presigned URLs via asyncio.gather
# ===========================================================================


class TestM36PresignedURLGather:

    @pytest.mark.asyncio
    async def test_get_all_users_uses_asyncio_gather(self) -> None:
        from app.api.v1.endpoints.users import get_all_users

        source = inspect.getsource(get_all_users)
        assert "asyncio.gather" in source

    def test_gather_wraps_all_user_conversions(self) -> None:
        from app.api.v1.endpoints.users import get_all_users

        source = inspect.getsource(get_all_users)
        assert "async_user_to_response(u)" in source
        assert "for u in users" in source

    def test_endpoint_imports_asyncio(self) -> None:
        import app.api.v1.endpoints.users as users_mod

        assert hasattr(users_mod, "asyncio")
