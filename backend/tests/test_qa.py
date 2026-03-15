"""Tests for Q&A service: best answer marking, voting, answer counts."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.errors import AppError

_SVC = "app.services.qa"
_VOTE_REPO = "app.repositories.vote_repo"


# --- Service: mark_best_answer ---


@pytest.mark.asyncio
async def test_mark_best_answer_success():
    from app.services.qa import mark_best_answer

    post_id = uuid.uuid4()
    comment_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    post_row = {
        "id": post_id,
        "user_id": uuid.UUID(user_id),
        "type": "question",
        "best_answer_id": None,
        "title": "Test Question",
    }
    comment_row = {
        "id": uuid.UUID(comment_id),
        "user_id": uuid.uuid4(),
        "post_id": post_id,
    }

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(side_effect=[post_row, comment_row, {"display_name": "User"}])
    mock_conn.execute = AsyncMock()

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
        patch(f"{_SVC}.get_pool", return_value=mock_pool),
        patch(f"{_SVC}.emit", new_callable=AsyncMock),
    ):
        result = await mark_best_answer(None, post_id, comment_id, user_id)
        assert result["post_id"] == str(post_id)
        assert result["best_answer_id"] == comment_id


@pytest.mark.asyncio
async def test_mark_best_answer_not_question():
    from app.services.qa import mark_best_answer

    post_id = uuid.uuid4()
    user_id = str(uuid.uuid4())

    post_row = {
        "id": post_id,
        "user_id": uuid.UUID(user_id),
        "type": "post",
        "best_answer_id": None,
        "title": "Regular Post",
    }

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=post_row)

    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    mock_conn.transaction = MagicMock(return_value=tx)

    mock_pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = cm

    with patch(f"{_SVC}.get_pool", return_value=mock_pool):
        with pytest.raises(AppError) as exc_info:
            await mark_best_answer(None, post_id, str(uuid.uuid4()), user_id)
        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_mark_best_answer_not_author():
    from app.services.qa import mark_best_answer

    post_id = uuid.uuid4()
    user_id = str(uuid.uuid4())
    other_user = str(uuid.uuid4())

    post_row = {
        "id": post_id,
        "user_id": uuid.UUID(other_user),
        "type": "question",
        "best_answer_id": None,
        "title": "Test",
    }

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=post_row)

    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    mock_conn.transaction = MagicMock(return_value=tx)

    mock_pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = cm

    with patch(f"{_SVC}.get_pool", return_value=mock_pool):
        with pytest.raises(AppError) as exc_info:
            await mark_best_answer(None, post_id, str(uuid.uuid4()), user_id)
        assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_mark_best_answer_post_not_found():
    from app.services.qa import mark_best_answer

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)

    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    mock_conn.transaction = MagicMock(return_value=tx)

    mock_pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = cm

    with patch(f"{_SVC}.get_pool", return_value=mock_pool):
        with pytest.raises(AppError) as exc_info:
            await mark_best_answer(None, uuid.uuid4(), str(uuid.uuid4()), str(uuid.uuid4()))
        assert exc_info.value.status_code == 404


# --- Service: unmark_best_answer ---


@pytest.mark.asyncio
async def test_unmark_best_answer_success():
    from app.services.qa import unmark_best_answer

    post_id = uuid.uuid4()
    user_id = str(uuid.uuid4())
    best_answer = uuid.uuid4()

    post_row = {
        "id": post_id,
        "user_id": uuid.UUID(user_id),
        "best_answer_id": best_answer,
    }

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=post_row)
    mock_conn.execute = AsyncMock()

    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    mock_conn.transaction = MagicMock(return_value=tx)

    mock_pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = cm

    with patch(f"{_SVC}.get_pool", return_value=mock_pool):
        result = await unmark_best_answer(None, post_id, user_id)
        assert result is True


@pytest.mark.asyncio
async def test_unmark_best_answer_nothing_to_unmark():
    from app.services.qa import unmark_best_answer

    post_id = uuid.uuid4()
    user_id = str(uuid.uuid4())

    post_row = {
        "id": post_id,
        "user_id": uuid.UUID(user_id),
        "best_answer_id": None,
    }

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=post_row)

    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    mock_conn.transaction = MagicMock(return_value=tx)

    mock_pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = cm

    with patch(f"{_SVC}.get_pool", return_value=mock_pool):
        result = await unmark_best_answer(None, post_id, user_id)
        assert result is True


# --- Service: vote_on_answer ---


@pytest.mark.asyncio
async def test_vote_on_answer_success():
    from app.services.qa import vote_on_answer

    comment_id = uuid.uuid4()
    user_id = str(uuid.uuid4())
    comment_owner = str(uuid.uuid4())

    comment_row = {
        "id": comment_id,
        "user_id": uuid.UUID(comment_owner),
        "post_id": uuid.uuid4(),
        "post_type": "question",
    }

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=comment_row)

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
        patch(f"{_SVC}.get_pool", return_value=mock_pool),
        patch(f"{_SVC}.check_rate_limit", new_callable=AsyncMock, return_value=True),
        patch(f"{_VOTE_REPO}.upsert_vote", new_callable=AsyncMock, return_value=1),
    ):
        result = await vote_on_answer(None, comment_id, user_id, 1)
        assert result["comment_id"] == str(comment_id)
        assert result["vote_score"] == 1
        assert result["your_vote"] == 1


@pytest.mark.asyncio
async def test_vote_on_own_answer_blocked():
    from app.services.qa import vote_on_answer

    comment_id = uuid.uuid4()
    user_id = str(uuid.uuid4())

    comment_row = {
        "id": comment_id,
        "user_id": uuid.UUID(user_id),  # Same user
        "post_id": uuid.uuid4(),
        "post_type": "question",
    }

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=comment_row)

    mock_pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = cm

    with (
        patch(f"{_SVC}.get_pool", return_value=mock_pool),
        patch(f"{_SVC}.check_rate_limit", new_callable=AsyncMock, return_value=True),
    ):
        with pytest.raises(AppError) as exc_info:
            await vote_on_answer(None, comment_id, user_id, 1)
        assert "QA_002" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_vote_on_non_question_blocked():
    from app.services.qa import vote_on_answer

    comment_id = uuid.uuid4()
    user_id = str(uuid.uuid4())

    comment_row = {
        "id": comment_id,
        "user_id": uuid.uuid4(),
        "post_id": uuid.uuid4(),
        "post_type": "post",  # Not a question
    }

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=comment_row)

    mock_pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = cm

    with (
        patch(f"{_SVC}.get_pool", return_value=mock_pool),
        patch(f"{_SVC}.check_rate_limit", new_callable=AsyncMock, return_value=True),
    ):
        with pytest.raises(AppError) as exc_info:
            await vote_on_answer(None, comment_id, user_id, 1)
        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_vote_rate_limited():
    from app.services.qa import vote_on_answer

    mock_pool = MagicMock()

    with (
        patch(f"{_SVC}.get_pool", return_value=mock_pool),
        patch(f"{_SVC}.check_rate_limit", new_callable=AsyncMock, return_value=False),
    ):
        with pytest.raises(AppError) as exc_info:
            await vote_on_answer(None, uuid.uuid4(), str(uuid.uuid4()), 1)
        assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_vote_comment_not_found():
    from app.services.qa import vote_on_answer

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)

    mock_pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = cm

    with (
        patch(f"{_SVC}.get_pool", return_value=mock_pool),
        patch(f"{_SVC}.check_rate_limit", new_callable=AsyncMock, return_value=True),
    ):
        with pytest.raises(AppError) as exc_info:
            await vote_on_answer(None, uuid.uuid4(), str(uuid.uuid4()), 1)
        assert exc_info.value.status_code == 404


# --- Service: get_user_votes ---


@pytest.mark.asyncio
async def test_get_user_votes():
    from app.services.qa import get_user_votes

    post_id = uuid.uuid4()
    user_id = str(uuid.uuid4())
    vote_rows = [
        {"comment_id": uuid.uuid4(), "vote": 1},
        {"comment_id": uuid.uuid4(), "vote": -1},
    ]

    mock_conn = AsyncMock()
    mock_pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = cm

    with (
        patch(f"{_SVC}.get_pool", return_value=mock_pool),
        patch(
            f"{_VOTE_REPO}.get_user_votes_for_post",
            new_callable=AsyncMock,
            return_value=vote_rows,
        ),
    ):
        result = await get_user_votes(None, post_id, user_id)
        assert len(result) == 2
        assert result[0]["vote"] == 1
        assert result[1]["vote"] == -1


# --- Post type filter tests ---


@pytest.mark.asyncio
async def test_post_create_request_type_validation():
    from app.schemas.post import PostCreateRequest

    # Valid types
    req = PostCreateRequest(title="Test", content="Content", type="post")
    assert req.type == "post"

    req = PostCreateRequest(title="Test", content="Content", type="question")
    assert req.type == "question"


@pytest.mark.asyncio
async def test_post_response_includes_qa_fields():
    from app.schemas.post import PostResponse

    resp = PostResponse(
        id="test",
        title="Test",
        content="Content",
        author={"id": "1", "username": "u", "display_name": "U"},
        version=1,
        comment_count=0,
        type="question",
        citation_count=3,
        answer_count=5,
        best_answer_id="abc-123",
        created_at="2024-01-01",
        updated_at="2024-01-01",
    )
    assert resp.type == "question"
    assert resp.citation_count == 3
    assert resp.answer_count == 5
    assert resp.best_answer_id == "abc-123"
