"""Tests for cascade delete fixes: album, form, post citations, and comment children."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Album cascade delete (D3) ───────────────────────────────────────────────


class TestAlbumCascadeDelete:
    """D3: Album deletion should clean up photos, comments, members, and storage."""

    @pytest.mark.anyio
    async def test_delete_album_cascades_photos_comments_members(
        self, mock_pool, mock_conn
    ):
        """delete_album cleans up photos, comments, members, and refunds storage."""
        from app.services.album import delete_album

        user_id = str(uuid.uuid4())
        album_id = str(uuid.uuid4())

        album_row = {
            "id": uuid.UUID(album_id),
            "created_by": uuid.UUID(user_id),
            "is_deleted": False,
            "title": "Test",
            "description": None,
            "created_by_name": "User",
            "photo_count": 2,
            "member_count": 1,
            "cover_photo_url": None,
            "is_archived": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        uploader_id = uuid.UUID(user_id)
        photos = [
            {
                "id": uuid.uuid4(),
                "storage_key": "albums/photo1.jpg",
                "thumbnail_key": "albums/thumb1.webp",
                "file_size_bytes": 1024,
                "uploaded_by": uploader_id,
            },
            {
                "id": uuid.uuid4(),
                "storage_key": "albums/photo2.jpg",
                "thumbnail_key": None,
                "file_size_bytes": 2048,
                "uploaded_by": uploader_id,
            },
        ]

        with (
            patch("app.services.album.get_pool", return_value=mock_pool),
            patch(
                "app.repositories.album_repo.find_album_by_id",
                new_callable=AsyncMock,
                return_value=album_row,
            ),
            patch(
                "app.repositories.album_repo.find_all_photos_for_album",
                new_callable=AsyncMock,
                return_value=photos,
            ),
            patch(
                "app.repositories.album_repo.soft_delete_album",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_soft_del,
            patch(
                "app.repositories.album_repo.delete_all_comments_for_album",
                new_callable=AsyncMock,
                return_value=5,
            ) as mock_del_comments,
            patch(
                "app.repositories.album_repo.delete_all_photos_for_album",
                new_callable=AsyncMock,
                return_value=2,
            ) as mock_del_photos,
            patch(
                "app.repositories.album_repo.delete_all_members_for_album",
                new_callable=AsyncMock,
                return_value=1,
            ) as mock_del_members,
            patch("app.core.storage.delete_file") as mock_delete_file,
        ):
            result = await delete_album(album_id, user_id, "SUPER_ADMIN")

            assert result is True
            mock_soft_del.assert_called_once()
            mock_del_comments.assert_called_once()
            mock_del_photos.assert_called_once()
            mock_del_members.assert_called_once()

            # Storage cleanup: 2 storage_keys + 1 thumbnail (photo2 has None thumbnail)
            assert mock_delete_file.call_count == 3

            # Verify storage quota refund was called via conn.execute
            # (3072 bytes total for uploader_id)
            execute_calls = mock_conn.execute.call_args_list
            quota_calls = [
                c
                for c in execute_calls
                if "storage_used_bytes" in str(c)
            ]
            assert len(quota_calls) == 1
            # Total refund: 1024 + 2048 = 3072
            assert quota_calls[0].args[1] == 3072

    @pytest.mark.anyio
    async def test_delete_album_not_found(self, mock_pool, mock_conn):
        """delete_album raises AppError if album not found."""
        from app.core.errors import AppError
        from app.services.album import delete_album

        with (
            patch("app.services.album.get_pool", return_value=mock_pool),
            patch(
                "app.repositories.album_repo.find_album_by_id",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            with pytest.raises(AppError):
                await delete_album(str(uuid.uuid4()), str(uuid.uuid4()), "SUPER_ADMIN")

    @pytest.mark.anyio
    async def test_delete_album_forbidden(self, mock_pool, mock_conn):
        """delete_album raises 403 for non-creator non-super-admin."""
        from app.core.errors import AppError
        from app.services.album import delete_album

        user_id = str(uuid.uuid4())
        other_user = str(uuid.uuid4())
        album_row = {
            "id": uuid.uuid4(),
            "created_by": uuid.UUID(other_user),
            "is_deleted": False,
            "title": "Test",
            "description": None,
            "created_by_name": "User",
            "photo_count": 0,
            "member_count": 1,
            "cover_photo_url": None,
            "is_archived": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        with (
            patch("app.services.album.get_pool", return_value=mock_pool),
            patch(
                "app.repositories.album_repo.find_album_by_id",
                new_callable=AsyncMock,
                return_value=album_row,
            ),
        ):
            with pytest.raises(AppError):
                await delete_album(str(uuid.uuid4()), user_id, "MEMBER")


# ── Form cascade delete (D4) ────────────────────────────────────────────────


class TestFormCascadeDelete:
    """D4: Form soft-delete should also delete form_responses."""

    @pytest.mark.anyio
    async def test_soft_delete_with_permission_deletes_responses(
        self, mock_pool, mock_conn
    ):
        """soft_delete_with_permission deletes form_responses inside transaction."""
        from app.repositories.form_repo import soft_delete_with_permission

        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        form_row = {
            "created_by": uuid.UUID(user_id),
            "banner_url": "forms/banners/test.jpg",
        }
        mock_conn.fetchrow.return_value = form_row

        with patch("app.repositories.form_repo.get_pool", return_value=mock_pool):
            deleted, banner_url = await soft_delete_with_permission(
                form_id, user_id, is_admin=False
            )

        assert deleted is True
        assert banner_url == "forms/banners/test.jpg"

        # Verify execute was called for both soft-delete and response cleanup
        execute_calls = mock_conn.execute.call_args_list
        soft_delete_call = [c for c in execute_calls if "is_deleted = true" in str(c)]
        response_delete_call = [c for c in execute_calls if "form_responses" in str(c)]
        assert len(soft_delete_call) >= 1
        assert len(response_delete_call) >= 1

    @pytest.mark.anyio
    async def test_soft_delete_with_permission_not_found(
        self, mock_pool, mock_conn
    ):
        """Returns (False, None) when form not found."""
        from app.repositories.form_repo import soft_delete_with_permission

        mock_conn.fetchrow.return_value = None

        with patch("app.repositories.form_repo.get_pool", return_value=mock_pool):
            deleted, banner_url = await soft_delete_with_permission(
                uuid.uuid4(), str(uuid.uuid4()), is_admin=False
            )

        assert deleted is False
        assert banner_url is None

    @pytest.mark.anyio
    async def test_soft_delete_with_permission_denied(
        self, mock_pool, mock_conn
    ):
        """Raises PermissionError when non-admin non-creator tries to delete."""
        from app.repositories.form_repo import soft_delete_with_permission

        creator_id = str(uuid.uuid4())
        other_user = str(uuid.uuid4())

        form_row = {
            "created_by": uuid.UUID(creator_id),
            "banner_url": None,
        }
        mock_conn.fetchrow.return_value = form_row

        with patch("app.repositories.form_repo.get_pool", return_value=mock_pool):
            with pytest.raises(PermissionError):
                await soft_delete_with_permission(
                    uuid.uuid4(), other_user, is_admin=False
                )


# ── Post citation cleanup (D5) ──────────────────────────────────────────────


class TestPostCitationCleanup:
    """D5: Post soft-delete should clean up post_citations."""

    @pytest.mark.anyio
    async def test_soft_delete_post_cleans_citations(self, mock_pool, mock_conn):
        """soft_delete_post deletes citations when post is deleted."""
        from app.services.post import soft_delete_post

        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        with (
            patch(
                "app.repositories.post_repo.soft_delete",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.services.post._cleanup_post_files",
                new_callable=AsyncMock,
            ),
            patch("app.services.post.get_pool", return_value=mock_pool),
        ):
            result = await soft_delete_post(post_id, user_id, is_admin=False)

        assert result is True
        # Verify citation cleanup was called
        execute_calls = mock_conn.execute.call_args_list
        citation_calls = [c for c in execute_calls if "post_citations" in str(c)]
        assert len(citation_calls) == 1
        # Verify it deletes both directions
        call_sql = str(citation_calls[0])
        assert "citing_post_id" in call_sql
        assert "cited_post_id" in call_sql

    @pytest.mark.anyio
    async def test_soft_delete_post_no_citation_cleanup_when_not_deleted(
        self, mock_pool, mock_conn
    ):
        """No citation cleanup when post soft-delete returns False."""
        from app.services.post import soft_delete_post

        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        with (
            patch(
                "app.repositories.post_repo.soft_delete",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            result = await soft_delete_post(post_id, user_id, is_admin=False)

        assert result is False
        # No pool acquire should happen for citation cleanup
        mock_conn.execute.assert_not_called()

    @pytest.mark.anyio
    async def test_soft_delete_post_citation_cleanup_failure_does_not_raise(
        self, mock_pool, mock_conn
    ):
        """Citation cleanup failure is swallowed (best-effort)."""
        from app.services.post import soft_delete_post

        post_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        mock_conn.execute.side_effect = Exception("DB error")

        with (
            patch(
                "app.repositories.post_repo.soft_delete",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.services.post._cleanup_post_files",
                new_callable=AsyncMock,
            ),
            patch("app.services.post.get_pool", return_value=mock_pool),
        ):
            result = await soft_delete_post(post_id, user_id, is_admin=False)

        assert result is True


# ── Comment child cascade (D6) ──────────────────────────────────────────────


class TestCommentChildCascade:
    """D6: Deleting a parent comment should soft-delete all children."""

    @pytest.mark.anyio
    async def test_parent_comment_delete_cascades_children(
        self, mock_pool, mock_conn
    ):
        """Deleting a top-level comment soft-deletes children and adjusts counts."""
        from app.repositories.comment_repo import soft_delete

        comment_id = uuid.uuid4()
        post_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # Parent comment (parent_id IS NULL)
        parent_row = MagicMock()
        parent_row.__getitem__ = lambda self, key: {
            "post_id": post_id,
            "parent_id": None,
        }[key]

        mock_conn.fetchrow.return_value = parent_row
        # Simulate 3 children deleted
        mock_conn.execute.return_value = "UPDATE 3"

        with patch("app.repositories.comment_repo.get_pool", return_value=mock_pool):
            result = await soft_delete(comment_id, post_id, user_id, is_admin=False)

        assert result == post_id

        execute_calls = mock_conn.execute.call_args_list
        # Should have: soft-delete children, decrement comment_count by 4, decrement answer_count
        child_delete_calls = [
            c for c in execute_calls if "parent_id = $1" in str(c)
        ]
        assert len(child_delete_calls) == 1

        # comment_count should be decremented by 4 (1 parent + 3 children)
        comment_count_calls = [
            c for c in execute_calls if "comment_count" in str(c)
        ]
        assert len(comment_count_calls) == 1
        assert comment_count_calls[0].args[1] == 4  # total_deleted

    @pytest.mark.anyio
    async def test_child_comment_delete_does_not_cascade(
        self, mock_pool, mock_conn
    ):
        """Deleting a child comment does NOT cascade to siblings."""
        from app.repositories.comment_repo import soft_delete

        comment_id = uuid.uuid4()
        post_id = uuid.uuid4()
        parent_id = uuid.uuid4()
        user_id = uuid.uuid4()

        child_row = MagicMock()
        child_row.__getitem__ = lambda self, key: {
            "post_id": post_id,
            "parent_id": parent_id,
        }[key]

        mock_conn.fetchrow.return_value = child_row
        mock_conn.execute.return_value = "UPDATE 1"

        with patch("app.repositories.comment_repo.get_pool", return_value=mock_pool):
            result = await soft_delete(comment_id, post_id, user_id, is_admin=False)

        assert result == post_id

        execute_calls = mock_conn.execute.call_args_list
        # No child cascade for child comments
        child_cascade_calls = [
            c for c in execute_calls if "parent_id = $1" in str(c)
        ]
        assert len(child_cascade_calls) == 0

        # comment_count decremented by 1 only
        comment_count_calls = [
            c for c in execute_calls if "comment_count" in str(c)
        ]
        assert len(comment_count_calls) == 1
        assert comment_count_calls[0].args[1] == 1

        # No answer_count decrement for child
        answer_count_calls = [
            c for c in execute_calls if "answer_count" in str(c)
        ]
        assert len(answer_count_calls) == 0

    @pytest.mark.anyio
    async def test_parent_delete_with_no_children(self, mock_pool, mock_conn):
        """Parent comment with 0 children still works correctly."""
        from app.repositories.comment_repo import soft_delete

        comment_id = uuid.uuid4()
        post_id = uuid.uuid4()

        parent_row = MagicMock()
        parent_row.__getitem__ = lambda self, key: {
            "post_id": post_id,
            "parent_id": None,
        }[key]

        mock_conn.fetchrow.return_value = parent_row
        mock_conn.execute.return_value = "UPDATE 0"

        with patch("app.repositories.comment_repo.get_pool", return_value=mock_pool):
            result = await soft_delete(comment_id, post_id, is_admin=True)

        assert result == post_id

        execute_calls = mock_conn.execute.call_args_list
        comment_count_calls = [
            c for c in execute_calls if "comment_count" in str(c)
        ]
        assert len(comment_count_calls) == 1
        # 1 parent + 0 children = 1
        assert comment_count_calls[0].args[1] == 1


# ── Form deadline validation (B3) ───────────────────────────────────────────


class TestFormDeadlineValidation:
    """B3: Form creation/update rejects past deadlines."""

    @pytest.mark.anyio
    async def test_create_form_past_deadline_rejected(self):
        """create_form raises AppError for a deadline in the past."""
        from app.core.errors import AppError
        from app.services.form import create_form

        past = datetime.now(timezone.utc) - timedelta(hours=1)

        with pytest.raises(AppError) as exc_info:
            await create_form(
                sig_id=None,
                user_id=str(uuid.uuid4()),
                title="Test",
                description=None,
                banner_url=None,
                deadline=past,
                max_respondents=None,
                questions=[{"id": "q1", "type": "text", "label": "Name"}],
            )

        assert exc_info.value.status_code == 400
        assert "future" in str(exc_info.value.detail).lower()

    @pytest.mark.anyio
    async def test_create_form_future_deadline_allowed(self, mock_pool, mock_conn):
        """create_form accepts a deadline in the future."""
        from app.services.form import create_form

        future = datetime.now(timezone.utc) + timedelta(days=7)
        user_id = str(uuid.uuid4())

        form_row = {
            "id": uuid.uuid4(),
            "sig_id": None,
            "created_by": uuid.UUID(user_id),
            "title": "Test",
            "description": None,
            "banner_url": None,
            "deadline": future,
            "max_respondents": None,
            "questions": '[{"id": "q1", "type": "text", "label": "Name"}]',
            "is_schema_locked": False,
            "allow_non_members": True,
            "is_deleted": False,
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "creator_display_name": "Test User",
        }

        mock_conn.fetchrow.side_effect = [
            MagicMock(
                __getitem__=lambda s, k: {"cnt": 0}[k]
            ),  # count_active_standalone
            form_row,  # insert RETURNING
            MagicMock(
                __getitem__=lambda s, k: {"display_name": "Test User"}[k]
            ),  # creator lookup
        ]

        with (
            patch("app.repositories.form_repo.get_pool", return_value=mock_pool),
            patch("app.services.form.get_pool", return_value=mock_pool),
        ):
            result = await create_form(
                sig_id=None,
                user_id=user_id,
                title="Test",
                description=None,
                banner_url=None,
                deadline=future,
                max_respondents=None,
                questions=[{"id": "q1", "type": "text", "label": "Name"}],
            )

        assert result is not None

    @pytest.mark.anyio
    async def test_update_form_past_deadline_rejected(self, mock_pool, mock_conn):
        """update_form raises AppError for a deadline in the past."""
        from app.core.errors import AppError
        from app.services.form import update_form

        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        past = datetime.now(timezone.utc) - timedelta(hours=1)

        current_form = {
            "id": form_id,
            "created_by": uuid.UUID(user_id),
            "is_schema_locked": False,
            "title": "Test",
            "deadline": None,
            "questions": "[]",
        }
        mock_conn.fetchrow.return_value = current_form

        with (
            patch("app.services.form.get_pool", return_value=mock_pool),
            patch(
                "app.repositories.form_repo.find_for_update",
                new_callable=AsyncMock,
                return_value=current_form,
            ),
        ):
            with pytest.raises(AppError) as exc_info:
                await update_form(
                    form_id, user_id, is_admin=False, deadline=past
                )

            assert exc_info.value.status_code == 400
            assert "future" in str(exc_info.value.detail).lower()


# ── Locked form schema error (B5) ───────────────────────────────────────────


class TestLockedFormSchemaError:
    """B5: Updating questions on a locked form should raise an error."""

    @pytest.mark.anyio
    async def test_locked_form_questions_update_raises_error(
        self, mock_pool, mock_conn
    ):
        """update_form raises AppError when questions are modified on a locked form."""
        from app.core.errors import AppError
        from app.services.form import update_form

        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        current_form = {
            "id": form_id,
            "created_by": uuid.UUID(user_id),
            "is_schema_locked": True,
            "title": "Test",
            "deadline": None,
            "questions": '[{"id": "q1", "type": "text", "label": "Name"}]',
        }

        with (
            patch("app.services.form.get_pool", return_value=mock_pool),
            patch(
                "app.repositories.form_repo.find_for_update",
                new_callable=AsyncMock,
                return_value=current_form,
            ),
        ):
            with pytest.raises(AppError) as exc_info:
                await update_form(
                    form_id,
                    user_id,
                    is_admin=False,
                    questions=[{"id": "q2", "type": "text", "label": "New Q"}],
                )

            assert exc_info.value.status_code == 400
            assert "locked" in str(exc_info.value.detail).lower()

    @pytest.mark.anyio
    async def test_locked_form_non_question_update_allowed(
        self, mock_pool, mock_conn
    ):
        """update_form allows updating title on a locked form."""
        from app.services.form import update_form

        form_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        current_form = {
            "id": form_id,
            "created_by": uuid.UUID(user_id),
            "is_schema_locked": True,
            "title": "Old Title",
            "deadline": None,
            "questions": '[{"id": "q1", "type": "text", "label": "Name"}]',
        }

        updated_form = dict(current_form)
        updated_form["title"] = "New Title"
        updated_form["creator_display_name"] = "Test User"
        updated_form["created_at"] = datetime.now(timezone.utc)
        updated_form["updated_at"] = datetime.now(timezone.utc)

        with (
            patch("app.services.form.get_pool", return_value=mock_pool),
            patch(
                "app.repositories.form_repo.find_for_update",
                new_callable=AsyncMock,
                return_value=current_form,
            ),
            patch(
                "app.repositories.form_repo.update",
                new_callable=AsyncMock,
                return_value=(updated_form, 5),
            ),
        ):
            result = await update_form(
                form_id, user_id, is_admin=False, title="New Title"
            )

        assert result is not None
        assert result["title"] == "New Title"
