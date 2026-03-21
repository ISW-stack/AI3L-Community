"""Tests for the /co-authors/posts/{post_id}/all endpoint and related repo/service functions."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

_SVC = "app.services.co_author"
_REPO = "app.repositories.co_author_repo"


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


def _make_co_author_row(post_id=None, user_id=None, status="ACCEPTED"):
    now = datetime.now(timezone.utc)
    return {
        "id": uuid.uuid4(),
        "post_id": post_id or uuid.uuid4(),
        "user_id": user_id or uuid.uuid4(),
        "display_name": "Test User",
        "affiliation": None,
        "orcid": None,
        "is_external": False,
        "status": status,
        "invited_by": uuid.uuid4(),
        "invited_at": now,
        "responded_at": now if status != "PENDING" else None,
        "user_display_name": "Test User",
        "user_avatar_url": None,
    }


# --- Repository tests ---


@pytest.mark.asyncio
async def test_find_all_co_authors_by_post(mock_conn):
    """find_all_co_authors_by_post returns co-authors of ALL statuses."""
    from app.repositories import co_author_repo

    post_id = uuid.uuid4()
    rows = [
        _make_co_author_row(post_id=post_id, status="ACCEPTED"),
        _make_co_author_row(post_id=post_id, status="PENDING"),
        _make_co_author_row(post_id=post_id, status="REJECTED"),
    ]
    mock_conn.fetch = AsyncMock(return_value=rows)
    result = await co_author_repo.find_all_co_authors_by_post(mock_conn, post_id)
    assert len(result) == 3

    # Verify the query does NOT filter by status
    call_args = mock_conn.fetch.call_args
    query = call_args[0][0]
    assert "status" not in query.lower() or "status = 'ACCEPTED'" not in query


@pytest.mark.asyncio
async def test_find_all_co_authors_by_post_no_status_filter(mock_conn):
    """Ensure the SQL query does not contain a status filter."""
    from app.repositories import co_author_repo

    post_id = uuid.uuid4()
    mock_conn.fetch = AsyncMock(return_value=[])
    await co_author_repo.find_all_co_authors_by_post(mock_conn, post_id)

    call_args = mock_conn.fetch.call_args
    query = call_args[0][0]
    assert "status" not in query, "find_all_co_authors_by_post should not filter by status"


@pytest.mark.asyncio
async def test_find_all_co_authors_by_post_empty(mock_conn):
    """Returns empty list when no co-authors exist."""
    from app.repositories import co_author_repo

    mock_conn.fetch = AsyncMock(return_value=[])
    result = await co_author_repo.find_all_co_authors_by_post(mock_conn, uuid.uuid4())
    assert result == []


# --- Service tests ---


@pytest.mark.asyncio
async def test_service_list_all_co_authors():
    """list_all_co_authors returns co-authors of all statuses."""
    from app.services.co_author import list_all_co_authors

    post_id = uuid.uuid4()
    rows = [
        _make_co_author_row(post_id=post_id, status="ACCEPTED"),
        _make_co_author_row(post_id=post_id, status="PENDING"),
    ]
    with (
        patch(f"{_SVC}.get_pool") as mock_pool,
        patch(
            f"{_REPO}.find_all_co_authors_by_post",
            new_callable=AsyncMock,
            return_value=rows,
        ),
    ):
        conn = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.return_value.acquire.return_value = cm

        result = await list_all_co_authors(post_id, user_id=str(uuid.uuid4()), is_admin=True)
        assert len(result) == 2
        assert result[0]["post_id"] == str(post_id)


@pytest.mark.asyncio
async def test_service_list_all_co_authors_uses_correct_repo():
    """list_all_co_authors calls find_all_co_authors_by_post, not find_co_authors_by_post."""
    from app.services.co_author import list_all_co_authors

    post_id = uuid.uuid4()
    with (
        patch(f"{_SVC}.get_pool") as mock_pool,
        patch(
            f"{_REPO}.find_all_co_authors_by_post",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_find_all,
        patch(
            f"{_REPO}.find_co_authors_by_post",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_find_accepted,
    ):
        conn = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.return_value.acquire.return_value = cm

        await list_all_co_authors(post_id, user_id=str(uuid.uuid4()), is_admin=True)
        mock_find_all.assert_called_once()
        mock_find_accepted.assert_not_called()


# --- Endpoint tests ---


@pytest.mark.asyncio
async def test_list_all_co_authors_endpoint_requires_member(client):
    """GET /co-authors/posts/{post_id}/all requires MEMBER+ role."""
    # No auth override — should fail
    post_id = uuid.uuid4()
    resp = await client.get(f"/api/v1/co-authors/posts/{post_id}/all")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_all_co_authors_endpoint_success(client):
    """GET /co-authors/posts/{post_id}/all returns co-authors when authenticated."""
    _override_auth("MEMBER")
    post_id = uuid.uuid4()
    mock_result = [
        {
            "id": str(uuid.uuid4()),
            "post_id": str(post_id),
            "user_id": str(uuid.uuid4()),
            "display_name": "Test User",
            "affiliation": None,
            "orcid": None,
            "is_external": False,
            "status": "PENDING",
            "avatar_url": None,
            "invited_at": datetime.now(timezone.utc).isoformat(),
            "responded_at": None,
        },
    ]
    try:
        with patch(
            "app.api.v1.endpoints.co_authors.list_all_co_authors",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await client.get(f"/api/v1/co-authors/posts/{post_id}/all")
            assert resp.status_code == 200
            data = resp.json()
            assert "co_authors" in data
            assert len(data["co_authors"]) == 1
            assert data["co_authors"][0]["status"] == "PENDING"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_list_all_co_authors_endpoint_guest_rejected(client):
    """GET /co-authors/posts/{post_id}/all rejects GUEST role."""
    _override_auth("GUEST")
    post_id = uuid.uuid4()
    try:
        resp = await client.get(f"/api/v1/co-authors/posts/{post_id}/all")
        assert resp.status_code == 403
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_list_all_co_authors_endpoint_admin_allowed(client):
    """GET /co-authors/posts/{post_id}/all allows ADMIN role."""
    _override_auth("ADMIN")
    post_id = uuid.uuid4()
    try:
        with patch(
            "app.api.v1.endpoints.co_authors.list_all_co_authors",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = await client.get(f"/api/v1/co-authors/posts/{post_id}/all")
            assert resp.status_code == 200
            assert resp.json()["co_authors"] == []
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_list_all_co_authors_endpoint_super_admin_allowed(client):
    """GET /co-authors/posts/{post_id}/all allows SUPER_ADMIN role."""
    _override_auth("SUPER_ADMIN")
    post_id = uuid.uuid4()
    try:
        with patch(
            "app.api.v1.endpoints.co_authors.list_all_co_authors",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = await client.get(f"/api/v1/co-authors/posts/{post_id}/all")
            assert resp.status_code == 200
    finally:
        _clear_overrides()
