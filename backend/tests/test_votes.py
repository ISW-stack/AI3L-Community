"""Tests for vote repository: upsert, remove, score calculation."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

# --- upsert_vote tests ---


@pytest.mark.asyncio
async def test_upsert_vote_new_upvote(mock_conn):
    from app.repositories import vote_repo

    mock_conn.fetchrow = AsyncMock(return_value={"vote_score": 1})
    result = await vote_repo.upsert_vote(mock_conn, uuid.uuid4(), uuid.uuid4(), 1)
    assert result == 1


@pytest.mark.asyncio
async def test_upsert_vote_new_downvote(mock_conn):
    from app.repositories import vote_repo

    mock_conn.fetchrow = AsyncMock(return_value={"vote_score": -1})
    result = await vote_repo.upsert_vote(mock_conn, uuid.uuid4(), uuid.uuid4(), -1)
    assert result == -1


@pytest.mark.asyncio
async def test_upsert_vote_remove_existing(mock_conn):
    """Removing a vote (vote=0) when one exists."""
    from app.repositories import vote_repo

    # First call: get existing vote
    mock_conn.fetchrow = AsyncMock(
        side_effect=[
            {"vote": 1},  # existing vote
            {"vote_score": 0},  # after removal
        ]
    )
    mock_conn.execute = AsyncMock()
    result = await vote_repo.upsert_vote(mock_conn, uuid.uuid4(), uuid.uuid4(), 0)
    assert result == 0
    mock_conn.execute.assert_called_once()  # DELETE


@pytest.mark.asyncio
async def test_upsert_vote_remove_nonexistent(mock_conn):
    """Removing a vote (vote=0) when none exists."""
    from app.repositories import vote_repo

    mock_conn.fetchrow = AsyncMock(
        side_effect=[
            None,  # no existing vote
            {"vote_score": 0},  # current score
        ]
    )
    result = await vote_repo.upsert_vote(mock_conn, uuid.uuid4(), uuid.uuid4(), 0)
    assert result == 0


# --- get_user_vote tests ---


@pytest.mark.asyncio
async def test_get_user_vote_exists(mock_conn):
    from app.repositories import vote_repo

    mock_conn.fetchrow = AsyncMock(return_value={"vote": 1})
    result = await vote_repo.get_user_vote(mock_conn, uuid.uuid4(), uuid.uuid4())
    assert result == 1


@pytest.mark.asyncio
async def test_get_user_vote_not_exists(mock_conn):
    from app.repositories import vote_repo

    mock_conn.fetchrow = AsyncMock(return_value=None)
    result = await vote_repo.get_user_vote(mock_conn, uuid.uuid4(), uuid.uuid4())
    assert result is None


# --- get_user_votes_for_post tests ---


@pytest.mark.asyncio
async def test_get_user_votes_for_post(mock_conn):
    from app.repositories import vote_repo

    rows = [
        {"comment_id": uuid.uuid4(), "vote": 1},
        {"comment_id": uuid.uuid4(), "vote": -1},
    ]
    mock_conn.fetch = AsyncMock(return_value=rows)
    result = await vote_repo.get_user_votes_for_post(mock_conn, uuid.uuid4(), uuid.uuid4())
    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_user_votes_for_post_empty(mock_conn):
    from app.repositories import vote_repo

    mock_conn.fetch = AsyncMock(return_value=[])
    result = await vote_repo.get_user_votes_for_post(mock_conn, uuid.uuid4(), uuid.uuid4())
    assert result == []


# --- delete_by_user_id tests ---


@pytest.mark.asyncio
async def test_delete_by_user_id(mock_conn):
    from app.repositories import vote_repo

    mock_conn.execute = AsyncMock(return_value="DELETE 5")
    result = await vote_repo.delete_by_user_id(mock_conn, uuid.uuid4())
    assert result == 5


@pytest.mark.asyncio
async def test_delete_by_user_id_none(mock_conn):
    from app.repositories import vote_repo

    mock_conn.execute = AsyncMock(return_value="DELETE 0")
    result = await vote_repo.delete_by_user_id(mock_conn, uuid.uuid4())
    assert result == 0
