"""Tests for profile view recording, dedup, and counter updates."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_SVC = "app.services.profile_view"
_REPO = "app.repositories.profile_view_repo"


# --- Repository tests ---


@pytest.mark.asyncio
async def test_upsert_view_new_viewer(mock_conn):
    from app.repositories import profile_view_repo

    mock_conn.fetchrow = AsyncMock(return_value={"is_new": True})
    result = await profile_view_repo.upsert_view(mock_conn, uuid.uuid4(), uuid.uuid4())
    assert result is True
    mock_conn.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_upsert_view_returning_viewer(mock_conn):
    from app.repositories import profile_view_repo

    mock_conn.fetchrow = AsyncMock(return_value={"is_new": False})
    result = await profile_view_repo.upsert_view(mock_conn, uuid.uuid4(), uuid.uuid4())
    assert result is False


@pytest.mark.asyncio
async def test_increment_total_counter(mock_conn):
    from app.repositories import profile_view_repo

    mock_conn.execute = AsyncMock()
    await profile_view_repo.increment_total_counter(mock_conn, uuid.uuid4())
    mock_conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_increment_unique_counter(mock_conn):
    from app.repositories import profile_view_repo

    mock_conn.execute = AsyncMock()
    await profile_view_repo.increment_unique_counter(mock_conn, uuid.uuid4())
    mock_conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_view_counts(mock_conn):
    from app.repositories import profile_view_repo

    mock_conn.fetchrow = AsyncMock(return_value={"unique_count": 10, "total_count": 50})
    unique, total = await profile_view_repo.get_view_counts(mock_conn, uuid.uuid4())
    assert unique == 10
    assert total == 50


@pytest.mark.asyncio
async def test_get_view_counts_not_found(mock_conn):
    from app.repositories import profile_view_repo

    mock_conn.fetchrow = AsyncMock(return_value=None)
    unique, total = await profile_view_repo.get_view_counts(mock_conn, uuid.uuid4())
    assert unique == 0
    assert total == 0


@pytest.mark.asyncio
async def test_delete_by_profile_or_viewer(mock_conn):
    from app.repositories import profile_view_repo

    mock_conn.execute = AsyncMock(return_value="DELETE 5")
    result = await profile_view_repo.delete_by_profile_or_viewer(mock_conn, uuid.uuid4())
    assert result == 5


# --- Service tests ---


@pytest.mark.asyncio
async def test_record_profile_view_self_view():
    """Self-views should be skipped."""
    from app.services.profile_view import record_profile_view

    user_id = str(uuid.uuid4())
    # Should return without doing anything — get_redis is imported inline
    with patch("app.core.redis.get_redis") as mock_redis:
        await record_profile_view(None, None, user_id, user_id)
        mock_redis.assert_not_called()


@pytest.mark.asyncio
async def test_record_profile_view_dedup():
    """Already-viewed should be skipped (Redis returns None for nx)."""
    from app.services.profile_view import record_profile_view

    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=None)  # Key already exists

    with (
        patch("app.core.redis.get_redis", return_value=mock_redis),
        patch("app.core.database.get_pool") as mock_pool,
    ):
        await record_profile_view(None, None, str(uuid.uuid4()), str(uuid.uuid4()))
        # Pool should not be acquired since Redis dedup returned None
        mock_pool.return_value.acquire.assert_not_called()


@pytest.mark.asyncio
async def test_record_profile_view_new_viewer():
    """New viewer should trigger DB upsert and counter increments."""
    from app.services.profile_view import record_profile_view

    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)  # New key

    mock_conn = AsyncMock()
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    mock_conn.transaction = MagicMock(return_value=tx)

    mock_pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = cm

    with (
        patch("app.core.redis.get_redis", return_value=mock_redis),
        patch(f"{_SVC}.get_pool", return_value=mock_pool),
        patch(f"{_REPO}.upsert_view", new_callable=AsyncMock, return_value=True),
        patch(f"{_REPO}.increment_total_counter", new_callable=AsyncMock) as mock_total,
        patch(f"{_REPO}.increment_unique_counter", new_callable=AsyncMock) as mock_unique,
    ):
        await record_profile_view(None, None, str(uuid.uuid4()), str(uuid.uuid4()))
        mock_total.assert_called_once()
        mock_unique.assert_called_once()


@pytest.mark.asyncio
async def test_record_profile_view_returning_viewer():
    """Returning viewer should increment total but not unique."""
    from app.services.profile_view import record_profile_view

    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)

    mock_conn = AsyncMock()
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    mock_conn.transaction = MagicMock(return_value=tx)

    mock_pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = cm

    with (
        patch("app.core.redis.get_redis", return_value=mock_redis),
        patch(f"{_SVC}.get_pool", return_value=mock_pool),
        patch(f"{_REPO}.upsert_view", new_callable=AsyncMock, return_value=False),
        patch(f"{_REPO}.increment_total_counter", new_callable=AsyncMock) as mock_total,
        patch(f"{_REPO}.increment_unique_counter", new_callable=AsyncMock) as mock_unique,
    ):
        await record_profile_view(None, None, str(uuid.uuid4()), str(uuid.uuid4()))
        mock_total.assert_called_once()
        mock_unique.assert_not_called()
