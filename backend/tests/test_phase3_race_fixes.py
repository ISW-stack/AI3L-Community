"""Tests for Phase 3 medium-severity race condition and atomicity fixes.

M-08: Album upload_cover quota check + increment in same transaction
M-09: Post soft_delete + citation cleanup atomic in one transaction
M-10: Album add_member/join_album check+insert inside transaction
M-11: Album delete_photo deletes DB before storage
M-16: Form update can clear optional fields (deadline, description) to null
M-17: DM dm_friends_only check uses transaction connection (not separate)
"""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.errors import AppError

_ALBUM_SVC = "app.services.album"
_POST_SVC = "app.services.post"
_FORM_SVC = "app.services.form"
_DM_SVC = "app.services.dm"

_NOW = datetime.now(timezone.utc)


def _mock_pool_conn():
    """Create a mock pool + conn + transaction context manager triple."""
    conn = AsyncMock()
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)

    pool = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx

    return pool, conn


def _make_album_row(album_id=None, created_by=None, cover_photo_url=None):
    uid = created_by or uuid.uuid4()
    return {
        "id": album_id or uuid.uuid4(),
        "title": "Test Album",
        "description": "A test",
        "cover_photo_url": cover_photo_url,
        "created_by": uid,
        "created_by_name": "Test User",
        "is_archived": False,
        "photo_count": 1,
        "member_count": 1,
        "created_at": _NOW,
        "updated_at": _NOW,
    }


def _make_photo_row(photo_id=None, album_id=None, uploaded_by=None):
    return {
        "id": photo_id or uuid.uuid4(),
        "album_id": album_id or uuid.uuid4(),
        "uploaded_by": uploaded_by or uuid.uuid4(),
        "uploaded_by_name": "Uploader",
        "storage_key": "albums/x/photos/y.jpg",
        "original_filename": "test.jpg",
        "file_size_bytes": 2048,
        "content_type": "image/jpeg",
        "thumbnail_key": "albums/x/thumbs/y.jpg",
        "description": None,
        "width": None,
        "height": None,
        "is_zip": False,
        "created_at": _NOW,
        "updated_at": _NOW,
    }


# ── M-08: upload_cover quota check + increment in same transaction ────────


class TestUploadCoverQuotaAtomic:
    """M-08: Quota FOR UPDATE and increment happen in the same transaction."""

    @pytest.mark.anyio
    async def test_upload_cover_quota_check_and_increment_single_transaction(self):
        """Quota check (FOR UPDATE) and storage increment happen in Phase 3
        (same transaction), not in a separate Phase 1 transaction."""
        from app.services.album import upload_cover

        album_id = uuid.uuid4()
        user_id = uuid.uuid4()
        album_row = _make_album_row(album_id=album_id, created_by=user_id)

        # Phase 1 pool/conn (permissions only)
        pool1, conn1 = _mock_pool_conn()

        # Phase 3 pool/conn (quota + increment)
        conn3 = AsyncMock()
        tx3 = MagicMock()
        tx3.__aenter__ = AsyncMock(return_value=tx3)
        tx3.__aexit__ = AsyncMock(return_value=False)
        conn3.transaction = MagicMock(return_value=tx3)
        conn3.fetchrow = AsyncMock(return_value={"storage_used_bytes": 0})
        conn3.execute = AsyncMock(return_value="UPDATE 1")

        # Track which conn gets called. Pool returns conn1 first, then conn3, then conn1 again
        call_count = 0

        def _acquire_side_effect():
            nonlocal call_count
            call_count += 1
            ctx = MagicMock()
            if call_count == 1:
                ctx.__aenter__ = AsyncMock(return_value=conn1)
            elif call_count == 2:
                ctx.__aenter__ = AsyncMock(return_value=conn3)
            else:
                ctx.__aenter__ = AsyncMock(return_value=conn1)
            ctx.__aexit__ = AsyncMock(return_value=False)
            return ctx

        pool1.acquire.side_effect = _acquire_side_effect

        with (
            patch(f"{_ALBUM_SVC}.get_pool", return_value=pool1),
            patch(f"{_ALBUM_SVC}.validate_magic_number", return_value=True),
            patch(
                f"{_ALBUM_SVC}.album_repo.find_album_by_id",
                new_callable=AsyncMock,
                return_value=album_row,
            ),
            patch(
                f"{_ALBUM_SVC}.album_repo.find_member",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.core.async_storage.upload_file",
                new_callable=AsyncMock,
            ),
            patch(
                f"{_ALBUM_SVC}.album_repo.set_cover_photo",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.converters.album_converter.generate_presigned_url",
                return_value="http://url",
            ),
        ):
            await upload_cover(
                album_id=str(album_id),
                user_id=str(user_id),
                user_role="ADMIN",
                file_data=b"\xff\xd8\xff\xe0" + b"\x00" * 100,
                filename="cover.jpg",
                content_type="image/jpeg",
            )

        # Phase 3 conn (conn3) should have both FOR UPDATE query and increment
        # The fetchrow call is the FOR UPDATE quota check
        conn3.fetchrow.assert_called_once()
        assert "FOR UPDATE" in conn3.fetchrow.call_args[0][0]
        # The execute call is the storage increment
        assert conn3.execute.call_count >= 1

    @pytest.mark.anyio
    async def test_upload_cover_quota_exceeded_cleans_up_minio(self):
        """When quota is exceeded in Phase 3, the already-uploaded MinIO file
        is cleaned up."""
        from app.services.album import upload_cover

        album_id = uuid.uuid4()
        user_id = uuid.uuid4()
        album_row = _make_album_row(album_id=album_id, created_by=user_id)

        pool, conn = _mock_pool_conn()
        # Quota is maxed out
        conn.fetchrow.return_value = {"storage_used_bytes": 2_000_000_000}

        with (
            patch(f"{_ALBUM_SVC}.get_pool", return_value=pool),
            patch(f"{_ALBUM_SVC}.validate_magic_number", return_value=True),
            patch(
                f"{_ALBUM_SVC}.album_repo.find_album_by_id",
                new_callable=AsyncMock,
                return_value=album_row,
            ),
            patch(f"{_ALBUM_SVC}.album_repo.find_member", new_callable=AsyncMock, return_value=None),
            patch(
                "app.core.async_storage.upload_file",
                new_callable=AsyncMock,
            ) as mock_upload,
            patch(
                "app.core.async_storage.delete_file",
                new_callable=AsyncMock,
            ) as mock_delete,
        ):
            with pytest.raises(AppError) as exc_info:
                await upload_cover(
                    album_id=str(album_id),
                    user_id=str(user_id),
                    user_role="ADMIN",
                    file_data=b"\xff\xd8\xff\xe0" + b"\x00" * 100,
                    filename="cover.jpg",
                    content_type="image/jpeg",
                )
            assert exc_info.value.status_code == 400
            assert "quota" in exc_info.value.detail["message"].lower()
            # Upload happened (Phase 2) but then file should be cleaned up
            mock_upload.assert_called_once()
            mock_delete.assert_called_once()


# ── M-09: Post soft_delete + citation cleanup atomic ─────────────────────


class TestPostSoftDeleteAtomic:
    """M-09: Post soft-delete and citation cleanup in one transaction."""

    @pytest.mark.anyio
    async def test_soft_delete_with_citations_single_transaction(self):
        """soft_delete_post runs both UPDATE and citation DELETE on the same conn."""
        from app.services.post import soft_delete_post

        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        pool, conn = _mock_pool_conn()
        conn.execute = AsyncMock(return_value="UPDATE 1")

        with (
            patch(f"{_POST_SVC}.get_pool", return_value=pool),
            patch(f"{_POST_SVC}._cleanup_post_files", new_callable=AsyncMock),
        ):
            result = await soft_delete_post(post_id, user_id)

        assert result is True
        # conn.execute called at least twice: soft-delete UPDATE + citation DELETE
        assert conn.execute.call_count >= 2
        calls = [str(c) for c in conn.execute.call_args_list]
        has_soft_delete = any("is_deleted = true" in c for c in calls)
        has_citation = any("post_citations" in c for c in calls)
        assert has_soft_delete, "Missing soft-delete SQL"
        assert has_citation, "Missing citation cleanup SQL"

    @pytest.mark.anyio
    async def test_soft_delete_admin_gets_owner_id(self):
        """Admin soft-delete retrieves post_owner_id from DB."""
        from app.services.post import soft_delete_post

        post_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        admin_id = str(uuid.uuid4())
        pool, conn = _mock_pool_conn()
        conn.fetchval = AsyncMock(return_value=owner_id)
        conn.execute = AsyncMock(return_value="UPDATE 1")

        with (
            patch(f"{_POST_SVC}.get_pool", return_value=pool),
            patch(f"{_POST_SVC}._cleanup_post_files", new_callable=AsyncMock),
            patch(f"{_POST_SVC}.emit", new_callable=AsyncMock),
        ):
            result = await soft_delete_post(post_id, admin_id, is_admin=True)

        assert result is True
        conn.fetchval.assert_called_once()

    @pytest.mark.anyio
    async def test_soft_delete_no_delete_skips_citation_cleanup(self):
        """If post not found/already deleted, citation cleanup is skipped."""
        from app.services.post import soft_delete_post

        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        pool, conn = _mock_pool_conn()
        conn.execute = AsyncMock(return_value="UPDATE 0")

        with patch(f"{_POST_SVC}.get_pool", return_value=pool):
            result = await soft_delete_post(post_id, user_id)

        assert result is False
        # Only called once (the soft-delete attempt), not for citations
        assert conn.execute.call_count == 1


# ── M-10: Album add_member/join_album transaction ────────────────────────


class TestAlbumMemberTransactionAtomic:
    """M-10: Check + insert wrapped in transaction."""

    @pytest.mark.anyio
    async def test_add_member_uses_transaction(self):
        """add_member wraps check + insert in conn.transaction()."""
        from app.services.album import add_member

        album_id = uuid.uuid4()
        user_id = uuid.uuid4()
        target_id = uuid.uuid4()
        album_row = _make_album_row(album_id=album_id, created_by=user_id)
        member_row = {
            "id": uuid.uuid4(),
            "album_id": album_id,
            "user_id": target_id,
            "role": "MEMBER",
            "status": "ACCEPTED",
            "joined_at": _NOW,
        }
        full_member_row = {
            **member_row,
            "display_name": "Target User",
            "username": "target",
            "avatar_url": None,
        }

        pool, conn = _mock_pool_conn()

        with (
            patch(f"{_ALBUM_SVC}.get_pool", return_value=pool),
            patch(
                f"{_ALBUM_SVC}.album_repo.find_album_by_id",
                new_callable=AsyncMock,
                return_value=album_row,
            ),
            patch(
                f"{_ALBUM_SVC}.album_repo.find_member",
                new_callable=AsyncMock,
                side_effect=[
                    {"role": "ADMIN", "status": "ACCEPTED"},  # caller is admin
                    None,  # target not yet a member
                ],
            ),
            patch(
                f"{_ALBUM_SVC}.album_repo.insert_member",
                new_callable=AsyncMock,
                return_value=member_row,
            ),
            patch(
                f"{_ALBUM_SVC}.album_repo.find_member_by_id_with_user",
                new_callable=AsyncMock,
                return_value=full_member_row,
            ),
            patch(
                "app.converters.album_converter.resolve_avatar_url",
                return_value=None,
            ),
        ):
            result = await add_member(
                album_id=str(album_id),
                user_id=str(user_id),
                target_user_id=str(target_id),
                user_role="MEMBER",
            )

        assert result is not None
        # Verify transaction was entered
        conn.transaction.assert_called_once()

    @pytest.mark.anyio
    async def test_join_album_uses_transaction(self):
        """join_album wraps check + insert in conn.transaction()."""
        from app.services.album import join_album

        album_id = uuid.uuid4()
        user_id = uuid.uuid4()
        album_row = _make_album_row(album_id=album_id)
        member_row = {
            "id": uuid.uuid4(),
            "album_id": album_id,
            "user_id": user_id,
            "role": "MEMBER",
            "status": "PENDING",
            "joined_at": _NOW,
        }

        pool, conn = _mock_pool_conn()

        with (
            patch(f"{_ALBUM_SVC}.get_pool", return_value=pool),
            patch(
                f"{_ALBUM_SVC}.album_repo.find_album_by_id",
                new_callable=AsyncMock,
                return_value=album_row,
            ),
            patch(
                f"{_ALBUM_SVC}.album_repo.find_member",
                new_callable=AsyncMock,
                return_value=None,  # not yet a member
            ),
            patch(
                f"{_ALBUM_SVC}.album_repo.insert_member",
                new_callable=AsyncMock,
                return_value=member_row,
            ),
        ):
            result = await join_album(str(album_id), str(user_id))

        assert result["status"] == "PENDING"
        conn.transaction.assert_called_once()

    @pytest.mark.anyio
    async def test_join_album_existing_member_raises_409(self):
        """join_album raises 409 for duplicate within transaction."""
        from app.services.album import join_album

        album_id = uuid.uuid4()
        user_id = uuid.uuid4()
        album_row = _make_album_row(album_id=album_id)

        pool, conn = _mock_pool_conn()

        with (
            patch(f"{_ALBUM_SVC}.get_pool", return_value=pool),
            patch(
                f"{_ALBUM_SVC}.album_repo.find_album_by_id",
                new_callable=AsyncMock,
                return_value=album_row,
            ),
            patch(
                f"{_ALBUM_SVC}.album_repo.find_member",
                new_callable=AsyncMock,
                return_value={"id": uuid.uuid4(), "status": "PENDING"},
            ),
        ):
            with pytest.raises(AppError) as exc_info:
                await join_album(str(album_id), str(user_id))
            assert exc_info.value.status_code == 409


# ── M-11: Album delete_photo — DB before storage ────────────────────────


class TestDeletePhotoDBFirst:
    """M-11: DB record is deleted before MinIO storage cleanup."""

    @pytest.mark.anyio
    async def test_delete_photo_db_then_storage(self):
        """delete_photo deletes DB record first, then cleans up storage."""
        from app.services.album import delete_photo

        album_id = uuid.uuid4()
        photo_id = uuid.uuid4()
        user_id = uuid.uuid4()
        photo_row = _make_photo_row(
            photo_id=photo_id, album_id=album_id, uploaded_by=user_id
        )
        album_row = _make_album_row(album_id=album_id, created_by=user_id)

        pool, conn = _mock_pool_conn()
        call_order: list[str] = []

        async def mock_delete_photo(c, pid):
            call_order.append("db_delete")
            return True

        async def mock_delete_file(key):
            call_order.append(f"minio_delete:{key}")

        async def mock_decrement(uid, size):
            call_order.append("quota_refund")

        with (
            patch(f"{_ALBUM_SVC}.get_pool", return_value=pool),
            patch(
                f"{_ALBUM_SVC}.album_repo.find_photo_by_id",
                new_callable=AsyncMock,
                return_value=photo_row,
            ),
            patch(
                f"{_ALBUM_SVC}.album_repo.find_album_by_id",
                new_callable=AsyncMock,
                return_value=album_row,
            ),
            patch(
                f"{_ALBUM_SVC}.album_repo.delete_photo",
                side_effect=mock_delete_photo,
            ),
            patch(
                "app.core.async_storage.delete_file",
                side_effect=mock_delete_file,
            ),
            patch(
                f"{_ALBUM_SVC}.user_repo.decrement_storage_used",
                side_effect=mock_decrement,
            ),
        ):
            result = await delete_photo(
                album_id=str(album_id),
                photo_id=str(photo_id),
                user_id=str(user_id),
                user_role="MEMBER",
            )

        assert result is True
        # DB delete must come before any MinIO delete
        assert call_order[0] == "db_delete"
        assert any(c.startswith("minio_delete") for c in call_order[1:])
        assert "quota_refund" in call_order

    @pytest.mark.anyio
    async def test_delete_photo_storage_failure_still_returns_true(self):
        """If MinIO delete fails, the DB delete still succeeds."""
        from app.services.album import delete_photo

        album_id = uuid.uuid4()
        photo_id = uuid.uuid4()
        user_id = uuid.uuid4()
        photo_row = _make_photo_row(
            photo_id=photo_id, album_id=album_id, uploaded_by=user_id
        )
        album_row = _make_album_row(album_id=album_id, created_by=user_id)

        pool, conn = _mock_pool_conn()

        with (
            patch(f"{_ALBUM_SVC}.get_pool", return_value=pool),
            patch(
                f"{_ALBUM_SVC}.album_repo.find_photo_by_id",
                new_callable=AsyncMock,
                return_value=photo_row,
            ),
            patch(
                f"{_ALBUM_SVC}.album_repo.find_album_by_id",
                new_callable=AsyncMock,
                return_value=album_row,
            ),
            patch(
                f"{_ALBUM_SVC}.album_repo.delete_photo",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.core.async_storage.delete_file",
                new_callable=AsyncMock,
                side_effect=Exception("MinIO down"),
            ),
            patch(
                f"{_ALBUM_SVC}.user_repo.decrement_storage_used",
                new_callable=AsyncMock,
                side_effect=Exception("DB error"),
            ),
        ):
            result = await delete_photo(
                album_id=str(album_id),
                photo_id=str(photo_id),
                user_id=str(user_id),
                user_role="MEMBER",
            )

        # DB delete succeeded; storage/quota failures are non-fatal
        assert result is True


# ── M-16: Form update can clear optional fields to null ──────────────────


class TestFormUpdateClearFields:
    """M-16: update_form respects provided_fields to allow clearing to None."""

    @pytest.mark.anyio
    async def test_update_form_can_clear_deadline(self):
        """Passing deadline=None with 'deadline' in provided_fields clears it."""
        from app.services.form import update_form

        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        creator = uuid.UUID(user_id)

        current_form = {
            "id": form_id,
            "sig_id": None,
            "created_by": creator,
            "title": "Test Form",
            "description": "A test",
            "banner_url": None,
            "deadline": _NOW,
            "max_respondents": None,
            "questions": json.dumps([]),
            "allow_non_members": False,
            "is_closed": False,
            "is_schema_locked": False,
            "is_deleted": False,
            "created_at": _NOW,
            "updated_at": _NOW,
        }

        updated_form = {**current_form, "deadline": None}
        creator_row = {"display_name": "Test User"}

        pool, conn = _mock_pool_conn()

        with (
            patch(f"{_FORM_SVC}.get_pool", return_value=pool),
            patch(
                f"{_FORM_SVC}.form_repo.find_for_update",
                new_callable=AsyncMock,
                return_value=current_form,
            ),
            patch(
                f"{_FORM_SVC}.form_repo.update",
                new_callable=AsyncMock,
                return_value=(
                    {**updated_form, "creator_display_name": "Test User"},
                    0,
                ),
            ) as mock_update,
        ):
            result = await update_form(
                form_id=form_id,
                user_id=user_id,
                is_admin=False,
                deadline=None,
                provided_fields={"deadline"},
            )

        assert result is not None
        # Verify that the update was called with deadline=None in updates dict
        mock_update.assert_called_once()
        updates_arg = mock_update.call_args[0][1]  # second positional arg
        assert "deadline" in updates_arg
        assert updates_arg["deadline"] is None

    @pytest.mark.anyio
    async def test_update_form_can_clear_description(self):
        """Passing description=None with 'description' in provided_fields clears it."""
        from app.services.form import update_form

        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        creator = uuid.UUID(user_id)

        current_form = {
            "id": form_id,
            "sig_id": None,
            "created_by": creator,
            "title": "Test Form",
            "description": "Existing description",
            "banner_url": None,
            "deadline": None,
            "max_respondents": None,
            "questions": json.dumps([]),
            "allow_non_members": False,
            "is_closed": False,
            "is_schema_locked": False,
            "is_deleted": False,
            "created_at": _NOW,
            "updated_at": _NOW,
        }

        pool, conn = _mock_pool_conn()

        with (
            patch(f"{_FORM_SVC}.get_pool", return_value=pool),
            patch(
                f"{_FORM_SVC}.form_repo.find_for_update",
                new_callable=AsyncMock,
                return_value=current_form,
            ),
            patch(
                f"{_FORM_SVC}.form_repo.update",
                new_callable=AsyncMock,
                return_value=(
                    {**current_form, "description": None, "creator_display_name": "Test"},
                    0,
                ),
            ) as mock_update,
        ):
            result = await update_form(
                form_id=form_id,
                user_id=user_id,
                is_admin=False,
                description=None,
                provided_fields={"description"},
            )

        assert result is not None
        updates_arg = mock_update.call_args[0][1]
        assert "description" in updates_arg
        assert updates_arg["description"] is None

    @pytest.mark.anyio
    async def test_update_form_omitted_fields_not_cleared(self):
        """Fields not in provided_fields remain unchanged (not cleared to null)."""
        from app.services.form import update_form

        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        creator = uuid.UUID(user_id)

        current_form = {
            "id": form_id,
            "sig_id": None,
            "created_by": creator,
            "title": "Test Form",
            "description": "Keep this",
            "banner_url": None,
            "deadline": _NOW,
            "max_respondents": None,
            "questions": json.dumps([]),
            "allow_non_members": False,
            "is_closed": False,
            "is_schema_locked": False,
            "is_deleted": False,
            "created_at": _NOW,
            "updated_at": _NOW,
        }

        pool, conn = _mock_pool_conn()

        with (
            patch(f"{_FORM_SVC}.get_pool", return_value=pool),
            patch(
                f"{_FORM_SVC}.form_repo.find_for_update",
                new_callable=AsyncMock,
                return_value=current_form,
            ),
            patch(
                f"{_FORM_SVC}.form_repo.update",
                new_callable=AsyncMock,
                return_value=(
                    {**current_form, "title": "New Title", "creator_display_name": "Test"},
                    0,
                ),
            ) as mock_update,
        ):
            # Only title provided, deadline is None but NOT in provided_fields
            result = await update_form(
                form_id=form_id,
                user_id=user_id,
                is_admin=False,
                title="New Title",
                deadline=None,
                provided_fields={"title"},
            )

        assert result is not None
        updates_arg = mock_update.call_args[0][1]
        assert "title" in updates_arg
        # deadline should NOT be in updates because it wasn't in provided_fields
        assert "deadline" not in updates_arg


# ── M-17: DM dm_friends_only check uses transaction connection ───────────


class TestDMFriendsOnlyInline:
    """M-17: dm_friends_only check uses the same transaction connection."""

    @pytest.mark.anyio
    async def test_friends_only_check_inline(self):
        """send_message queries dm_friends_only on the same conn, not via repo."""
        from app.services.dm import send_message

        sender_id = str(uuid.uuid4())
        recipient_id = str(uuid.uuid4())

        pool, conn = _mock_pool_conn()
        # fetchval returns True for dm_friends_only
        conn.fetchval = AsyncMock(return_value=True)

        conv_row = {
            "id": uuid.uuid4(),
            "participant_a": uuid.UUID(sender_id),
            "participant_b": uuid.UUID(recipient_id),
            "total_chars": 0,
            "created_at": _NOW,
            "updated_at": _NOW,
        }

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.social_repo.find_friendship_between",
                new_callable=AsyncMock,
                return_value=None,  # not friends
            ),
        ):
            with pytest.raises(AppError) as exc_info:
                await send_message(
                    sender_id=sender_id,
                    recipient_id=recipient_id,
                    content="Hello!",
                )
            assert exc_info.value.status_code == 403
            assert "friends" in exc_info.value.detail["message"].lower()

        # The conn.fetchval should have been called with the dm_friends_only query
        fetchval_calls = conn.fetchval.call_args_list
        dm_query_found = any(
            "dm_friends_only" in str(c) and "user_preferences" in str(c)
            for c in fetchval_calls
        )
        assert dm_query_found, (
            "dm_friends_only should be queried inline on transaction conn, "
            "not via dm_repo.get_dm_friends_only (which opens a separate connection)"
        )

    @pytest.mark.anyio
    async def test_friends_only_false_allows_message(self):
        """When dm_friends_only is False, non-friends can send messages."""
        from app.services.dm import send_message

        sender_id = str(uuid.uuid4())
        recipient_id = str(uuid.uuid4())
        conv_id = uuid.uuid4()
        msg_id = uuid.uuid4()

        pool, conn = _mock_pool_conn()
        # fetchval returns False for dm_friends_only
        conn.fetchval = AsyncMock(return_value=False)

        msg_row = {
            "id": msg_id,
            "conversation_id": conv_id,
            "sender_id": uuid.UUID(sender_id),
            "content": "Hello!",
            "attachment_key": None,
            "attachment_name": None,
            "attachment_size": None,
            "attachment_expires_at": None,
            "is_recalled": False,
            "is_edited": False,
            "read_at": None,
            "created_at": _NOW,
            "updated_at": _NOW,
            "sender_display_name": "Sender",
            "sender_avatar_url": None,
        }

        conv_row = {
            "id": conv_id,
            "participant_a": uuid.UUID(sender_id),
            "participant_b": uuid.UUID(recipient_id),
            "total_chars": 0,
            "created_at": _NOW,
            "updated_at": _NOW,
        }

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.dm_repo.find_or_create_conversation",
                new_callable=AsyncMock,
                return_value=conv_row,
            ),
            patch(
                "app.repositories.dm_repo.send_message_atomic",
                new_callable=AsyncMock,
                return_value=(msg_row, []),
            ),
            patch("app.services.dm.emit", new_callable=AsyncMock),
        ):
            result = await send_message(
                sender_id=sender_id,
                recipient_id=recipient_id,
                content="Hello!",
            )

        assert result["id"] == str(msg_id)

    @pytest.mark.anyio
    async def test_friends_only_true_friends_allowed(self):
        """When dm_friends_only is True and users are friends, message goes through."""
        from app.services.dm import send_message

        sender_id = str(uuid.uuid4())
        recipient_id = str(uuid.uuid4())
        conv_id = uuid.uuid4()
        msg_id = uuid.uuid4()

        pool, conn = _mock_pool_conn()
        conn.fetchval = AsyncMock(return_value=True)

        msg_row = {
            "id": msg_id,
            "conversation_id": conv_id,
            "sender_id": uuid.UUID(sender_id),
            "content": "Hi friend!",
            "attachment_key": None,
            "attachment_name": None,
            "attachment_size": None,
            "attachment_expires_at": None,
            "is_recalled": False,
            "is_edited": False,
            "read_at": None,
            "created_at": _NOW,
            "updated_at": _NOW,
            "sender_display_name": "Sender",
            "sender_avatar_url": None,
        }

        conv_row = {
            "id": conv_id,
            "participant_a": uuid.UUID(sender_id),
            "participant_b": uuid.UUID(recipient_id),
            "total_chars": 0,
            "created_at": _NOW,
            "updated_at": _NOW,
        }

        with (
            patch("app.core.database.get_pool", return_value=pool),
            patch(
                "app.repositories.social_repo.is_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.repositories.social_repo.find_friendship_between",
                new_callable=AsyncMock,
                return_value={"status": "ACCEPTED"},
            ),
            patch(
                "app.repositories.dm_repo.find_or_create_conversation",
                new_callable=AsyncMock,
                return_value=conv_row,
            ),
            patch(
                "app.repositories.dm_repo.send_message_atomic",
                new_callable=AsyncMock,
                return_value=(msg_row, []),
            ),
            patch("app.services.dm.emit", new_callable=AsyncMock),
        ):
            result = await send_message(
                sender_id=sender_id,
                recipient_id=recipient_id,
                content="Hi friend!",
            )

        assert result["id"] == str(msg_id)
