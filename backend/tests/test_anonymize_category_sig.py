"""Tests for M3 (anonymize album cleanup), M7 (category duplicate name), M11 (SIG album cascade N/A)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.errors import ConflictError


@pytest.mark.anyio
async def test_anonymize_cleans_album_data(mock_pool, mock_conn):
    """M3: anonymize_user should execute album_members DELETE, album_comments soft-delete,
    and album_photos uploaded_by NULL within the transaction."""
    user_id = uuid.uuid4()

    # user_repo.anonymize returns True (user was anonymized)
    with (
        patch("app.services.user.user_repo") as mock_repo,
        patch("app.core.database.get_pool", return_value=mock_pool),
    ):
        mock_repo.anonymize = AsyncMock(return_value=True)

        from app.services.user import anonymize_user

        result = await anonymize_user(user_id)

    assert result is True

    # Collect all SQL executed on the mock connection
    executed_sqls = [call.args[0] for call in mock_conn.execute.call_args_list]

    # Verify album cleanup SQL was executed
    assert any(
        "DELETE FROM album_members" in sql for sql in executed_sqls
    ), "Expected DELETE FROM album_members"
    assert any(
        "UPDATE album_comments SET is_deleted = true" in sql for sql in executed_sqls
    ), "Expected album_comments soft-delete"
    assert any(
        "UPDATE album_photos SET uploaded_by = NULL" in sql for sql in executed_sqls
    ), "Expected album_photos uploaded_by nullification"


@pytest.mark.anyio
async def test_category_update_rejects_duplicate_name(mock_pool, mock_conn):
    """M7: update_category should raise ConflictError when another category has the same name."""
    cat_id = uuid.uuid4()
    other_id = uuid.uuid4()

    # First fetchrow: current category exists
    # Second fetchrow: duplicate check returns a row (conflict)
    mock_conn.fetchrow = AsyncMock(
        side_effect=[
            {"id": cat_id, "name": "Old Name", "description": "desc"},
            {"id": other_id},  # duplicate found
        ]
    )

    with patch("app.services.category.get_pool", return_value=mock_pool):
        from app.services.category import update_category

        with pytest.raises(ConflictError, match="already exists"):
            await update_category(cat_id, name="Duplicate Name")


@pytest.mark.anyio
async def test_category_update_allows_same_name_same_id(mock_pool, mock_conn):
    """M7: updating a category with its own name should succeed (no false conflict)."""
    cat_id = uuid.uuid4()

    # First fetchrow: current category
    # Second fetchrow: duplicate check returns None (no conflict)
    # Third fetchrow: UPDATE RETURNING row
    mock_conn.fetchrow = AsyncMock(
        side_effect=[
            {"id": cat_id, "name": "Same Name", "description": "desc"},
            None,  # no duplicate
            {"id": cat_id, "name": "Same Name", "description": "updated desc"},
        ]
    )

    with patch("app.services.category.get_pool", return_value=mock_pool):
        from app.services.category import update_category

        result = await update_category(cat_id, name="Same Name", description="updated desc")

    assert result is not None
    assert result["name"] == "Same Name"


@pytest.mark.anyio
async def test_sig_soft_delete_no_album_cascade():
    """M11: Albums table has no sig_id FK — SIG soft_delete does not need album cleanup.

    This test documents that albums are standalone (no sig_id column), so
    sig_repo.soft_delete correctly omits album-related cascade operations.
    """
    # Verify by checking the soft_delete function source does not reference albums
    import inspect

    from app.repositories import sig_repo

    source = inspect.getsource(sig_repo.soft_delete)
    assert (
        "album" not in source.lower()
    ), "sig_repo.soft_delete should not reference albums — albums have no sig_id FK"
