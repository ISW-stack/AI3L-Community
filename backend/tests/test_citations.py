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
    result = await citation_repo.delete_citations(
        mock_conn, [uuid.uuid4(), uuid.uuid4()]
    )
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
