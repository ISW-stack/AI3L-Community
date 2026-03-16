"""Tests for cascade deletion fixes (H4 and M1)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.anyio
async def test_bulk_soft_delete_deletes_citations(mock_pool, mock_conn):
    """H4: bulk_soft_delete should delete citations for affected posts."""
    post_ids = [uuid.uuid4(), uuid.uuid4()]
    mock_conn.execute.return_value = "UPDATE 2"

    with patch("app.services.post.get_pool", return_value=mock_pool):
        with patch("app.services.post.post_repo") as mock_repo:
            mock_repo.bulk_soft_delete = AsyncMock(return_value=2)
            from app.services.post import bulk_soft_delete

            result = await bulk_soft_delete(post_ids)

    assert result == 2
    # Verify citation cleanup was called
    calls = mock_conn.execute.call_args_list
    citation_call = calls[0]
    assert "post_citations" in citation_call[0][0]
    assert post_ids == citation_call[0][1]


@pytest.mark.anyio
async def test_bulk_soft_delete_deletes_co_authors(mock_pool, mock_conn):
    """H4: bulk_soft_delete should delete co-authors for affected posts."""
    post_ids = [uuid.uuid4()]
    mock_conn.execute.return_value = "UPDATE 1"

    with patch("app.services.post.get_pool", return_value=mock_pool):
        with patch("app.services.post.post_repo") as mock_repo:
            mock_repo.bulk_soft_delete = AsyncMock(return_value=1)
            from app.services.post import bulk_soft_delete

            await bulk_soft_delete(post_ids)

    calls = mock_conn.execute.call_args_list
    co_author_call = calls[1]
    assert "post_co_authors" in co_author_call[0][0]
    assert post_ids == co_author_call[0][1]


@pytest.mark.anyio
async def test_bulk_soft_delete_soft_deletes_comments(mock_pool, mock_conn):
    """H4: bulk_soft_delete should soft-delete comments for affected posts."""
    post_ids = [uuid.uuid4(), uuid.uuid4()]
    mock_conn.execute.return_value = "UPDATE 3"

    with patch("app.services.post.get_pool", return_value=mock_pool):
        with patch("app.services.post.post_repo") as mock_repo:
            mock_repo.bulk_soft_delete = AsyncMock(return_value=2)
            from app.services.post import bulk_soft_delete

            await bulk_soft_delete(post_ids)

    calls = mock_conn.execute.call_args_list
    comment_call = calls[2]
    assert "comments" in comment_call[0][0]
    assert "is_deleted = true" in comment_call[0][0]
    assert post_ids == comment_call[0][1]


@pytest.mark.anyio
async def test_comment_soft_delete_clears_best_answer_id(mock_pool, mock_conn):
    """M1: comment soft_delete should clear best_answer_id when the deleted comment was the best answer."""
    comment_id = uuid.uuid4()
    post_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # The soft-delete UPDATE returns a row indicating success
    mock_conn.fetchrow.return_value = {"post_id": post_id, "parent_id": uuid.uuid4()}

    with patch("app.repositories.comment_repo.get_pool", return_value=mock_pool):
        from app.repositories.comment_repo import soft_delete

        result = await soft_delete(comment_id, post_id, user_id)

    assert result == post_id
    # Verify best_answer_id cleanup was called
    calls = mock_conn.execute.call_args_list
    best_answer_call = [c for c in calls if "best_answer_id" in c[0][0]]
    assert len(best_answer_call) == 1
    assert best_answer_call[0][0][1] == comment_id
