"""Tests for account deletion/anonymization cleanup completeness.

Covers:
- H-06: MinIO file deletion (avatar + DM attachments)
- M-42: Reactions JSONB user ID removal (posts + comments)
- M-43: post_history deletion
- M-44: privacy_consents deletion
- L-42: membership_applications and invite_codes deletion
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.anyio
class TestAnonymizePostHistory:
    """M-43: post_history rows should be deleted during anonymization."""

    async def test_post_history_deleted(self, mock_pool, mock_conn):
        user_id = uuid.uuid4()

        with (
            patch("app.services.user.user_repo") as mock_repo,
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch("app.services.user.async_delete_file", new_callable=AsyncMock),
        ):
            mock_repo.anonymize = AsyncMock(return_value=True)
            mock_repo.find_by_id = AsyncMock(return_value={"avatar_url": None})
            mock_conn.fetch = AsyncMock(return_value=[])

            from app.services.user import anonymize_user

            result = await anonymize_user(user_id)

        assert result["anonymized"] is True
        executed_sqls = [c.args[0] for c in mock_conn.execute.call_args_list if c.args]
        assert any(
            "DELETE FROM post_history" in sql and "post_id" in sql for sql in executed_sqls
        ), "Expected DELETE FROM post_history for user's posts"

    async def test_post_history_deleted_before_posts_soft_delete(self, mock_pool, mock_conn):
        """post_history must be deleted BEFORE posts are soft-deleted."""
        user_id = uuid.uuid4()

        with (
            patch("app.services.user.user_repo") as mock_repo,
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch("app.services.user.async_delete_file", new_callable=AsyncMock),
        ):
            mock_repo.anonymize = AsyncMock(return_value=True)
            mock_repo.find_by_id = AsyncMock(return_value={"avatar_url": None})
            mock_conn.fetch = AsyncMock(return_value=[])

            from app.services.user import anonymize_user

            await anonymize_user(user_id)

        executed_sqls = [c.args[0] for c in mock_conn.execute.call_args_list if c.args]
        history_idx = None
        posts_idx = None
        for i, sql in enumerate(executed_sqls):
            if "post_history" in sql:
                history_idx = i
            if "posts" in sql and "is_deleted = true" in sql:
                posts_idx = i
        assert history_idx is not None, "post_history DELETE should be present"
        assert posts_idx is not None, "posts soft-delete should be present"
        assert history_idx < posts_idx, "post_history must be deleted before posts are soft-deleted"


@pytest.mark.anyio
class TestAnonymizePrivacyConsents:
    """M-44: privacy_consents rows should be deleted during anonymization."""

    async def test_privacy_consents_deleted(self, mock_pool, mock_conn):
        user_id = uuid.uuid4()

        with (
            patch("app.services.user.user_repo") as mock_repo,
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch("app.services.user.async_delete_file", new_callable=AsyncMock),
        ):
            mock_repo.anonymize = AsyncMock(return_value=True)
            mock_repo.find_by_id = AsyncMock(return_value={"avatar_url": None})
            mock_conn.fetch = AsyncMock(return_value=[])

            from app.services.user import anonymize_user

            result = await anonymize_user(user_id)

        assert result["anonymized"] is True
        executed_sqls = [c.args[0] for c in mock_conn.execute.call_args_list if c.args]
        assert any(
            "DELETE FROM privacy_consents" in sql for sql in executed_sqls
        ), "Expected DELETE FROM privacy_consents"


@pytest.mark.anyio
class TestAnonymizeMembershipApplications:
    """L-42: membership_applications should be deleted during anonymization."""

    async def test_membership_applications_deleted(self, mock_pool, mock_conn):
        user_id = uuid.uuid4()

        with (
            patch("app.services.user.user_repo") as mock_repo,
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch("app.services.user.async_delete_file", new_callable=AsyncMock),
        ):
            mock_repo.anonymize = AsyncMock(return_value=True)
            mock_repo.find_by_id = AsyncMock(return_value={"avatar_url": None})
            mock_conn.fetch = AsyncMock(return_value=[])

            from app.services.user import anonymize_user

            result = await anonymize_user(user_id)

        assert result["anonymized"] is True
        executed_sqls = [c.args[0] for c in mock_conn.execute.call_args_list if c.args]
        assert any(
            "DELETE FROM membership_applications" in sql for sql in executed_sqls
        ), "Expected DELETE FROM membership_applications"


@pytest.mark.anyio
class TestAnonymizeInviteCodes:
    """L-42: invite_codes should be deleted during anonymization."""

    async def test_invite_codes_deleted(self, mock_pool, mock_conn):
        user_id = uuid.uuid4()

        with (
            patch("app.services.user.user_repo") as mock_repo,
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch("app.services.user.async_delete_file", new_callable=AsyncMock),
        ):
            mock_repo.anonymize = AsyncMock(return_value=True)
            mock_repo.find_by_id = AsyncMock(return_value={"avatar_url": None})
            mock_conn.fetch = AsyncMock(return_value=[])

            from app.services.user import anonymize_user

            result = await anonymize_user(user_id)

        assert result["anonymized"] is True
        executed_sqls = [c.args[0] for c in mock_conn.execute.call_args_list if c.args]
        assert any(
            "DELETE FROM invite_codes" in sql for sql in executed_sqls
        ), "Expected DELETE FROM invite_codes"


@pytest.mark.anyio
class TestAnonymizeReactionsCleanup:
    """M-42: User IDs should be removed from reactions JSONB in posts and comments."""

    async def test_reactions_cleaned_from_posts(self, mock_pool, mock_conn):
        user_id = uuid.uuid4()

        with (
            patch("app.services.user.user_repo") as mock_repo,
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch("app.services.user.async_delete_file", new_callable=AsyncMock),
        ):
            mock_repo.anonymize = AsyncMock(return_value=True)
            mock_repo.find_by_id = AsyncMock(return_value={"avatar_url": None})
            mock_conn.fetch = AsyncMock(return_value=[])

            from app.services.user import anonymize_user

            await anonymize_user(user_id)

        executed_sqls = [c.args[0] for c in mock_conn.execute.call_args_list if c.args]
        assert any(
            "UPDATE posts" in sql and "reactions" in sql and "jsonb_array_elements_text" in sql
            for sql in executed_sqls
        ), "Expected reactions cleanup SQL for posts"

    async def test_reactions_cleaned_from_comments(self, mock_pool, mock_conn):
        user_id = uuid.uuid4()

        with (
            patch("app.services.user.user_repo") as mock_repo,
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch("app.services.user.async_delete_file", new_callable=AsyncMock),
        ):
            mock_repo.anonymize = AsyncMock(return_value=True)
            mock_repo.find_by_id = AsyncMock(return_value={"avatar_url": None})
            mock_conn.fetch = AsyncMock(return_value=[])

            from app.services.user import anonymize_user

            await anonymize_user(user_id)

        executed_sqls = [c.args[0] for c in mock_conn.execute.call_args_list if c.args]
        assert any(
            "UPDATE comments" in sql and "reactions" in sql and "jsonb_array_elements_text" in sql
            for sql in executed_sqls
        ), "Expected reactions cleanup SQL for comments"

    async def test_reactions_cleanup_uses_user_id_string(self, mock_pool, mock_conn):
        """Reactions cleanup should pass user_id as string (reactions store string IDs)."""
        user_id = uuid.uuid4()

        with (
            patch("app.services.user.user_repo") as mock_repo,
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch("app.services.user.async_delete_file", new_callable=AsyncMock),
        ):
            mock_repo.anonymize = AsyncMock(return_value=True)
            mock_repo.find_by_id = AsyncMock(return_value={"avatar_url": None})
            mock_conn.fetch = AsyncMock(return_value=[])

            from app.services.user import anonymize_user

            await anonymize_user(user_id)

        # Find the reaction cleanup calls and verify they pass str(user_id)
        for c in mock_conn.execute.call_args_list:
            if c.args and "jsonb_array_elements_text" in str(c.args[0]):
                assert c.args[1] == str(user_id), "Reactions cleanup should pass user_id as string"


@pytest.mark.anyio
class TestAnonymizeMinIOCleanup:
    """H-06: MinIO files should be deleted on account deletion."""

    async def test_avatar_deleted_from_minio(self, mock_pool, mock_conn):
        """Avatar file should be deleted from MinIO after transaction."""
        user_id = uuid.uuid4()
        avatar_key = f"avatars/{user_id}/abc123.png"

        with (
            patch("app.services.user.user_repo") as mock_repo,
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch("app.services.user.async_delete_file", new_callable=AsyncMock) as mock_delete,
        ):
            mock_repo.find_by_id = AsyncMock(return_value={"avatar_url": avatar_key})
            mock_repo.anonymize = AsyncMock(return_value=True)
            mock_conn.fetch = AsyncMock(return_value=[])

            from app.services.user import anonymize_user

            await anonymize_user(user_id)

        mock_delete.assert_any_call(avatar_key)

    async def test_dm_attachments_deleted_from_minio(self, mock_pool, mock_conn):
        """DM attachment files should be deleted from MinIO after transaction."""
        user_id = uuid.uuid4()
        dm_key_1 = f"dm/{user_id}/file1.pdf"
        dm_key_2 = f"dm/{user_id}/file2.jpg"

        with (
            patch("app.services.user.user_repo") as mock_repo,
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch("app.services.user.async_delete_file", new_callable=AsyncMock) as mock_delete,
        ):
            mock_repo.find_by_id = AsyncMock(return_value={"avatar_url": None})
            mock_repo.anonymize = AsyncMock(return_value=True)
            # Return DM attachment rows from fetch
            mock_conn.fetch = AsyncMock(
                return_value=[
                    {"attachment_key": dm_key_1},
                    {"attachment_key": dm_key_2},
                ]
            )

            from app.services.user import anonymize_user

            await anonymize_user(user_id)

        mock_delete.assert_any_call(dm_key_1)
        mock_delete.assert_any_call(dm_key_2)

    async def test_no_minio_deletion_when_no_avatar(self, mock_pool, mock_conn):
        """No MinIO deletion attempted when user has no avatar and no DM attachments."""
        user_id = uuid.uuid4()

        with (
            patch("app.services.user.user_repo") as mock_repo,
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch("app.services.user.async_delete_file", new_callable=AsyncMock) as mock_delete,
        ):
            mock_repo.find_by_id = AsyncMock(return_value={"avatar_url": None})
            mock_repo.anonymize = AsyncMock(return_value=True)
            mock_conn.fetch = AsyncMock(return_value=[])

            from app.services.user import anonymize_user

            await anonymize_user(user_id)

        mock_delete.assert_not_called()

    async def test_http_avatar_url_skipped(self, mock_pool, mock_conn):
        """HTTP(S) avatar URLs should not be treated as MinIO keys."""
        user_id = uuid.uuid4()

        with (
            patch("app.services.user.user_repo") as mock_repo,
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch("app.services.user.async_delete_file", new_callable=AsyncMock) as mock_delete,
        ):
            mock_repo.find_by_id = AsyncMock(
                return_value={"avatar_url": "https://example.com/avatar.png"}
            )
            mock_repo.anonymize = AsyncMock(return_value=True)
            mock_conn.fetch = AsyncMock(return_value=[])

            from app.services.user import anonymize_user

            await anonymize_user(user_id)

        mock_delete.assert_not_called()

    async def test_minio_deletion_failure_does_not_raise(self, mock_pool, mock_conn):
        """MinIO deletion failure should be logged but not raise."""
        user_id = uuid.uuid4()
        avatar_key = f"avatars/{user_id}/abc.png"

        with (
            patch("app.services.user.user_repo") as mock_repo,
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch("app.services.user.async_delete_file", new_callable=AsyncMock) as mock_delete,
        ):
            mock_repo.find_by_id = AsyncMock(return_value={"avatar_url": avatar_key})
            mock_repo.anonymize = AsyncMock(return_value=True)
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_delete.side_effect = Exception("MinIO down")

            from app.services.user import anonymize_user

            # Should not raise despite MinIO failure
            result = await anonymize_user(user_id)

        assert result["anonymized"] is True

    async def test_avatar_and_dm_files_both_deleted(self, mock_pool, mock_conn):
        """Both avatar and DM attachment files should be deleted."""
        user_id = uuid.uuid4()
        avatar_key = f"avatars/{user_id}/abc.png"
        dm_key = f"dm/{user_id}/doc.pdf"

        with (
            patch("app.services.user.user_repo") as mock_repo,
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch("app.services.user.async_delete_file", new_callable=AsyncMock) as mock_delete,
        ):
            mock_repo.find_by_id = AsyncMock(return_value={"avatar_url": avatar_key})
            mock_repo.anonymize = AsyncMock(return_value=True)
            mock_conn.fetch = AsyncMock(return_value=[{"attachment_key": dm_key}])

            from app.services.user import anonymize_user

            await anonymize_user(user_id)

        assert mock_delete.call_count == 2
        mock_delete.assert_any_call(avatar_key)
        mock_delete.assert_any_call(dm_key)

    async def test_no_minio_cleanup_when_anonymize_fails(self, mock_pool, mock_conn):
        """When user_repo.anonymize returns False, no MinIO cleanup should happen."""
        user_id = uuid.uuid4()

        with (
            patch("app.services.user.user_repo") as mock_repo,
            patch("app.core.database.get_pool", return_value=mock_pool),
            patch("app.services.user.async_delete_file", new_callable=AsyncMock) as mock_delete,
        ):
            mock_repo.find_by_id = AsyncMock(
                return_value={"avatar_url": f"avatars/{user_id}/abc.png"}
            )
            mock_repo.anonymize = AsyncMock(return_value=False)

            from app.services.user import anonymize_user

            result = await anonymize_user(user_id)

        assert result["anonymized"] is False
        mock_delete.assert_not_called()
