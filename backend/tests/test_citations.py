"""Tests for citation parsing, sync, and endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_SVC = "app.services.citation"
_REPO = "app.repositories.citation_repo"


# --- Citation parser tests ---


def test_parse_cited_post_ids_basic():
    from app.services.citation import parse_cited_post_ids

    post_id = str(uuid.uuid4())
    html = f'<a href="/forum/{post_id}" data-citation="true">Ref</a>'
    result = parse_cited_post_ids(html)
    assert len(result) == 1
    assert str(result[0]) == post_id


def test_parse_cited_post_ids_multiple():
    from app.services.citation import parse_cited_post_ids

    id1 = str(uuid.uuid4())
    id2 = str(uuid.uuid4())
    html = (
        f'<a href="/forum/{id1}" data-citation="true">Ref1</a>'
        f'<a href="/posts/{id2}" data-citation="true">Ref2</a>'
    )
    result = parse_cited_post_ids(html)
    assert len(result) == 2


def test_parse_cited_post_ids_dedup():
    from app.services.citation import parse_cited_post_ids

    post_id = str(uuid.uuid4())
    html = (
        f'<a href="/forum/{post_id}" data-citation="true">Ref1</a>'
        f'<a href="/forum/{post_id}" data-citation="true">Ref2</a>'
    )
    result = parse_cited_post_ids(html)
    assert len(result) == 1


def test_parse_cited_post_ids_no_citation_attr():
    from app.services.citation import parse_cited_post_ids

    post_id = str(uuid.uuid4())
    html = f'<a href="/forum/{post_id}">Not a citation</a>'
    result = parse_cited_post_ids(html)
    assert len(result) == 0


def test_parse_cited_post_ids_invalid_uuid():
    from app.services.citation import parse_cited_post_ids

    html = '<a href="/forum/not-a-uuid" data-citation="true">Ref</a>'
    result = parse_cited_post_ids(html)
    assert len(result) == 0


def test_parse_cited_post_ids_empty_html():
    from app.services.citation import parse_cited_post_ids

    result = parse_cited_post_ids("")
    assert result == []


def test_parse_cited_post_ids_no_links():
    from app.services.citation import parse_cited_post_ids

    result = parse_cited_post_ids("<p>No links here</p>")
    assert result == []


# --- Repository tests ---


@pytest.mark.asyncio
async def test_insert_citation(mock_conn):
    from app.repositories import citation_repo

    now = datetime.now(timezone.utc)
    cid = uuid.uuid4()
    row = {
        "id": cid,
        "citing_post_id": uuid.uuid4(),
        "cited_post_id": uuid.uuid4(),
        "is_self_citation": False,
        "created_at": now,
    }
    mock_conn.fetchrow = AsyncMock(return_value=row)
    result = await citation_repo.insert_citation(
        mock_conn, cid, row["citing_post_id"], row["cited_post_id"], False
    )
    assert result["id"] == cid


@pytest.mark.asyncio
async def test_delete_citations(mock_conn):
    from app.repositories import citation_repo

    mock_conn.execute = AsyncMock(return_value="DELETE 2")
    result = await citation_repo.delete_citations(mock_conn, [uuid.uuid4(), uuid.uuid4()])
    assert result == 2


@pytest.mark.asyncio
async def test_delete_citations_empty(mock_conn):
    from app.repositories import citation_repo

    result = await citation_repo.delete_citations(mock_conn, [])
    assert result == 0


@pytest.mark.asyncio
async def test_find_existing_citations(mock_conn):
    from app.repositories import citation_repo

    rows = [
        {"id": uuid.uuid4(), "cited_post_id": uuid.uuid4()},
        {"id": uuid.uuid4(), "cited_post_id": uuid.uuid4()},
    ]
    mock_conn.fetch = AsyncMock(return_value=rows)
    result = await citation_repo.find_existing_citations(mock_conn, uuid.uuid4())
    assert len(result) == 2


@pytest.mark.asyncio
async def test_update_citation_count(mock_conn):
    from app.repositories import citation_repo

    mock_conn.fetchval = AsyncMock(return_value=5)
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")
    result = await citation_repo.update_citation_count(mock_conn, uuid.uuid4())
    assert result == 5


# --- post_process_citations test ---


def test_post_process_citations():
    from app.core.file_validation import post_process_citations

    html = '<a href="/forum/abc" data-citation="true">Ref</a>'
    result = post_process_citations(html)
    assert 'class="citation"' in result
    assert 'data-citation="true"' in result


def test_post_process_citations_no_citation():
    from app.core.file_validation import post_process_citations

    html = '<a href="/forum/abc">Normal link</a>'
    result = post_process_citations(html)
    assert 'class="citation"' not in result


# --- Bug fix tests ---


@pytest.mark.asyncio
async def test_search_posts_for_citation_excludes_blocked():
    """H6: search_posts_for_citation excludes posts by blocked users."""
    from app.services.citation import search_posts_for_citation

    user_id = str(uuid.uuid4())
    blocked_user_id = str(uuid.uuid4())

    # Two rows returned: one from blocked user, one from normal user
    normal_post_id = uuid.uuid4()
    all_rows = [
        {"id": normal_post_id, "title": "Normal Post", "author_name": "Normal User"},
    ]

    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=all_rows)

    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = cm

    with (
        patch(f"{_SVC}.get_pool", return_value=pool),
        patch(f"{_SVC}.get_redis") as _mock_redis,  # noqa: F841
        patch(
            f"{_SVC}.get_blocked_user_ids",
            new_callable=AsyncMock,
            return_value={blocked_user_id},
        ),
    ):
        result = await search_posts_for_citation("machine learning", user_id)
        assert len(result) == 1
        assert result[0]["title"] == "Normal Post"

        # Verify the query used the blocked-user exclusion clause
        call_args = conn.fetch.call_args
        query = call_args[0][0]
        assert "p.user_id != ALL" in query
        # The blocked UUID list should be the third parameter ($3)
        params = call_args[0][1:]
        assert "machine learning" in params
        # Verify blocked_uuids were passed
        assert any(
            isinstance(p, list) and len(p) == 1 for p in params
        ), f"Expected blocked UUID list in params, got: {params}"


@pytest.mark.asyncio
async def test_search_posts_for_citation_no_blocked():
    """H6: search_posts_for_citation works normally when no users are blocked."""
    from app.services.citation import search_posts_for_citation

    user_id = str(uuid.uuid4())
    rows = [
        {"id": uuid.uuid4(), "title": "Post 1", "author_name": "Author 1"},
    ]

    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=rows)

    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = cm

    with (
        patch(f"{_SVC}.get_pool", return_value=pool),
        patch(f"{_SVC}.get_redis") as _mock_redis,  # noqa: F841
        patch(
            f"{_SVC}.get_blocked_user_ids",
            new_callable=AsyncMock,
            return_value=set(),
        ),
    ):
        result = await search_posts_for_citation("test query", user_id)
        assert len(result) == 1

        # Verify the query does NOT include the blocked-user exclusion
        call_args = conn.fetch.call_args
        query = call_args[0][0]
        assert "p.user_id != ALL" not in query


@pytest.mark.asyncio
async def test_citation_event_includes_citer_id():
    """M6: post.cited event includes citer_id for trigger_user_id."""
    from app.services.citation import sync_post_citations

    post_id = uuid.uuid4()
    cited_id = uuid.uuid4()
    author_id = str(uuid.uuid4())
    cited_author_id = uuid.uuid4()  # Different from author

    html = f'<a href="/forum/{cited_id}" data-citation="true">Ref</a>'

    conn = AsyncMock()
    conn.fetchval = AsyncMock(side_effect=[1, cited_author_id])  # exists=1, cited_author

    # transaction context manager
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)

    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = cm

    # For the emit block's pool2.acquire
    citing_post_row = {"title": "Citing Post Title"}
    citer_row = {"display_name": "Author Name"}
    conn2 = AsyncMock()
    conn2.fetchrow = AsyncMock(side_effect=[citing_post_row, citer_row])
    cm2 = AsyncMock()
    cm2.__aenter__ = AsyncMock(return_value=conn2)
    cm2.__aexit__ = AsyncMock(return_value=False)

    pool_calls = [0]

    def get_pool_side_effect():
        pool_calls[0] += 1
        if pool_calls[0] <= 1:
            return pool
        pool2 = MagicMock()
        pool2.acquire.return_value = cm2
        return pool2

    citation_row = {
        "id": uuid.uuid4(),
        "citing_post_id": post_id,
        "cited_post_id": cited_id,
        "is_self_citation": False,
        "created_at": datetime.now(timezone.utc),
    }

    mock_emit = AsyncMock()

    with (
        patch(f"{_SVC}.get_pool", side_effect=get_pool_side_effect),
        patch(
            "app.repositories.citation_repo.find_existing_citations",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "app.repositories.citation_repo.insert_citation",
            new_callable=AsyncMock,
            return_value=citation_row,
        ),
        patch(
            "app.repositories.citation_repo.update_citation_count",
            new_callable=AsyncMock,
            return_value=1,
        ),
        patch(
            "app.repositories.citation_repo.delete_citations",
            new_callable=AsyncMock,
        ),
        patch(f"{_SVC}.emit", mock_emit),
    ):
        await sync_post_citations(post_id, html, author_id)

        # Verify emit was called with citer_id
        mock_emit.assert_called_once()
        call_kwargs = mock_emit.call_args[1]
        assert call_kwargs["citer_id"] == author_id
        assert call_kwargs["cited_post_id"] == str(cited_id)


# --- B4: Service functions no longer accept pool parameter ---


def test_sync_post_citations_no_pool_parameter():
    """B4: sync_post_citations no longer has pool parameter."""
    import inspect

    from app.services.citation import sync_post_citations

    sig = inspect.signature(sync_post_citations)
    param_names = list(sig.parameters.keys())
    assert "pool" not in param_names, "pool parameter should have been removed"
    assert param_names[0] == "post_id", "First parameter should be post_id"


def test_get_citations_of_no_pool_parameter():
    """B4: get_citations_of no longer has pool parameter."""
    import inspect

    from app.services.citation import get_citations_of

    sig = inspect.signature(get_citations_of)
    param_names = list(sig.parameters.keys())
    assert "pool" not in param_names, "pool parameter should have been removed"
    assert param_names[0] == "post_id", "First parameter should be post_id"


def test_get_citing_no_pool_parameter():
    """B4: get_citing no longer has pool parameter."""
    import inspect

    from app.services.citation import get_citing

    sig = inspect.signature(get_citing)
    param_names = list(sig.parameters.keys())
    assert "pool" not in param_names, "pool parameter should have been removed"
    assert param_names[0] == "post_id", "First parameter should be post_id"


def test_search_posts_for_citation_no_pool_parameter():
    """B4: search_posts_for_citation no longer has pool parameter."""
    import inspect

    from app.services.citation import search_posts_for_citation

    sig = inspect.signature(search_posts_for_citation)
    param_names = list(sig.parameters.keys())
    assert "pool" not in param_names, "pool parameter should have been removed"
    assert param_names[0] == "query", "First parameter should be query"


@pytest.mark.asyncio
async def test_get_citations_of_service():
    """B4: get_citations_of works without pool parameter."""
    from app.services.citation import get_citations_of

    now = datetime.now(timezone.utc)
    rows = [
        {
            "id": uuid.uuid4(),
            "post_id": uuid.uuid4(),
            "post_title": "Test Post",
            "author_name": "Test Author",
            "is_self_citation": False,
            "created_at": now,
        }
    ]

    conn = AsyncMock()
    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = cm

    with (
        patch(f"{_SVC}.get_pool", return_value=pool),
        patch(
            f"{_REPO}.find_citations_of_post",
            new_callable=AsyncMock,
            return_value=(rows, 1),
        ),
    ):
        result, total = await get_citations_of(post_id=uuid.uuid4())
        assert total == 1
        assert len(result) == 1
        assert result[0]["post_title"] == "Test Post"


@pytest.mark.asyncio
async def test_get_citing_service():
    """B4: get_citing works without pool parameter."""
    from app.services.citation import get_citing

    now = datetime.now(timezone.utc)
    rows = [
        {
            "id": uuid.uuid4(),
            "post_id": uuid.uuid4(),
            "post_title": "Referenced Post",
            "author_name": "Author",
            "is_self_citation": False,
            "created_at": now,
        }
    ]

    conn = AsyncMock()
    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = cm

    with (
        patch(f"{_SVC}.get_pool", return_value=pool),
        patch(
            f"{_REPO}.find_citations_by_post",
            new_callable=AsyncMock,
            return_value=(rows, 1),
        ),
    ):
        result, total = await get_citing(post_id=uuid.uuid4())
        assert total == 1
        assert len(result) == 1
        assert result[0]["post_title"] == "Referenced Post"
