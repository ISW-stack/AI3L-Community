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
    comment_id = uuid.uuid4()
    user_id = str(uuid.uuid4())

    post_row = {
        "id": post_id,
        "user_id": uuid.UUID(user_id),
        "type": "question",
        "best_answer_id": None,
        "title": "Test Question",
    }
    comment_row = {
        "id": comment_id,
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
        result = await mark_best_answer(post_id, comment_id, user_id)
        assert result["post_id"] == str(post_id)
        assert result["best_answer_id"] == str(comment_id)


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
            await mark_best_answer(post_id, uuid.uuid4(), user_id)
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
            await mark_best_answer(post_id, uuid.uuid4(), user_id)
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
            await mark_best_answer(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()))
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
        "type": "question",
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
        result = await unmark_best_answer(post_id, user_id)
        assert result is True


@pytest.mark.asyncio
async def test_unmark_best_answer_nothing_to_unmark():
    from app.services.qa import unmark_best_answer

    post_id = uuid.uuid4()
    user_id = str(uuid.uuid4())

    post_row = {
        "id": post_id,
        "user_id": uuid.UUID(user_id),
        "type": "question",
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
        result = await unmark_best_answer(post_id, user_id)
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
        result = await vote_on_answer(comment_id, user_id, 1)
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
    ):
        with pytest.raises(AppError) as exc_info:
            await vote_on_answer(comment_id, user_id, 1)
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
    ):
        with pytest.raises(AppError) as exc_info:
            await vote_on_answer(comment_id, user_id, 1)
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
            await vote_on_answer(uuid.uuid4(), str(uuid.uuid4()), 1)
        assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_vote_comment_not_found():
    from app.services.qa import vote_on_answer

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

    with (
        patch(f"{_SVC}.get_pool", return_value=mock_pool),
        patch(f"{_SVC}.check_rate_limit", new_callable=AsyncMock, return_value=True),
    ):
        with pytest.raises(AppError) as exc_info:
            await vote_on_answer(uuid.uuid4(), str(uuid.uuid4()), 1)
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
        result = await get_user_votes(post_id, user_id)
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


# --- C2: Converter includes Q&A fields ---


@pytest.mark.asyncio
async def test_converter_includes_vote_score():
    """C2: async_row_to_comment includes vote_score from row."""
    from app.converters.comment_converter import async_row_to_comment

    now = datetime.now(timezone.utc)
    row = {
        "id": uuid.uuid4(),
        "post_id": uuid.uuid4(),
        "content": "Answer text",
        "parent_id": None,
        "mentions": None,
        "reactions": {},
        "vote_score": 7,
        "is_best_answer": False,
        "created_at": now,
        "updated_at": now,
        "author_id": uuid.uuid4(),
        "author_username": "alice",
        "author_display_name": "Alice",
        "author_avatar_url": None,
    }

    with patch(
        "app.converters.shared.async_resolve_avatar_url", new_callable=AsyncMock, return_value=None
    ):
        result = await async_row_to_comment(row)

    assert result["vote_score"] == 7


@pytest.mark.asyncio
async def test_converter_includes_is_best_answer():
    """C2: row_to_comment includes is_best_answer from row."""
    from app.converters.comment_converter import row_to_comment

    now = datetime.now(timezone.utc)
    row = {
        "id": uuid.uuid4(),
        "post_id": uuid.uuid4(),
        "content": "Best answer text",
        "parent_id": None,
        "mentions": None,
        "reactions": {},
        "vote_score": 3,
        "is_best_answer": True,
        "created_at": now,
        "updated_at": now,
        "author_id": uuid.uuid4(),
        "author_username": "bob",
        "author_display_name": "Bob",
        "author_avatar_url": None,
    }

    with patch("app.converters.shared.resolve_avatar_url", return_value=None):
        result = row_to_comment(row)

    assert result["is_best_answer"] is True


# --- C3: answer_count increment/decrement ---


@pytest.mark.asyncio
async def test_answer_count_incremented_on_question_post():
    """C3: create_comment increments answer_count for top-level comments on question posts."""
    from app.services.comment import create_comment

    post_id = uuid.uuid4()
    comment_id = uuid.uuid4()
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    mock_post = {"id": post_id, "allow_comments": True, "comment_count": 0, "type": "question"}
    mock_row = {
        "id": comment_id,
        "post_id": post_id,
        "user_id": uuid.UUID(user_id),
        "parent_id": None,
        "content": "My answer",
        "mentions": None,
        "reactions": {},
        "created_at": now,
        "updated_at": now,
        "author_id": uuid.UUID(user_id),
        "author_username": "alice",
        "author_display_name": "Alice",
        "author_avatar_url": None,
    }

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[mock_post, mock_row])
    conn.execute = AsyncMock()

    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)

    mock_pool_obj = MagicMock()
    mock_pool_obj.acquire.return_value = cm

    mock_redis = AsyncMock()
    mock_redis.smembers = AsyncMock(return_value=set())

    with (
        patch("app.services.comment.get_pool", return_value=mock_pool_obj),
        patch("app.services.comment.emit", new_callable=AsyncMock),
        patch(
            "app.converters.shared.async_resolve_avatar_url",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.repositories.post_repo.find_owner_id", new_callable=AsyncMock, return_value=None
        ),
        patch("app.services.comment.get_redis", return_value=mock_redis),
    ):
        await create_comment(post_id=post_id, user_id=user_id, content="My answer")

    # conn.execute should have been called twice:
    # 1) comment_count + 1, 2) answer_count + 1
    execute_calls = conn.execute.call_args_list
    sql_calls = [call[0][0] for call in execute_calls]
    assert any(
        "answer_count = answer_count + 1" in sql for sql in sql_calls
    ), f"Expected answer_count increment SQL, got: {sql_calls}"


@pytest.mark.asyncio
async def test_answer_count_decremented_on_question_post_delete():
    """C3: soft_delete decrements answer_count for top-level comments on question posts."""
    from app.repositories.comment_repo import soft_delete

    comment_id = uuid.uuid4()
    post_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # Simulates a top-level comment (parent_id=None)
    delete_row = {"post_id": post_id, "parent_id": None}

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=delete_row)
    conn.execute = AsyncMock(return_value="UPDATE 0")

    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)

    mock_pool_obj = MagicMock()
    mock_pool_obj.acquire.return_value = cm

    with patch("app.repositories.comment_repo.get_pool", return_value=mock_pool_obj):
        result = await soft_delete(comment_id, post_id, user_id)

    assert result == post_id
    execute_calls = conn.execute.call_args_list
    sql_calls = [call[0][0] for call in execute_calls]
    assert any(
        "answer_count" in sql and "GREATEST" in sql and "question" in sql for sql in sql_calls
    ), f"Expected answer_count decrement SQL with GREATEST and question filter, got: {sql_calls}"


@pytest.mark.asyncio
async def test_answer_count_not_affected_for_regular_post():
    """C3: create_comment does NOT increment answer_count for regular (non-question) posts."""
    from app.services.comment import create_comment

    post_id = uuid.uuid4()
    comment_id = uuid.uuid4()
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    mock_post = {"id": post_id, "allow_comments": True, "comment_count": 0, "type": "post"}
    mock_row = {
        "id": comment_id,
        "post_id": post_id,
        "user_id": uuid.UUID(user_id),
        "parent_id": None,
        "content": "Regular comment",
        "mentions": None,
        "reactions": {},
        "created_at": now,
        "updated_at": now,
        "author_id": uuid.UUID(user_id),
        "author_username": "alice",
        "author_display_name": "Alice",
        "author_avatar_url": None,
    }

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[mock_post, mock_row])
    conn.execute = AsyncMock()

    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)

    mock_pool_obj = MagicMock()
    mock_pool_obj.acquire.return_value = cm

    mock_redis = AsyncMock()
    mock_redis.smembers = AsyncMock(return_value=set())

    with (
        patch("app.services.comment.get_pool", return_value=mock_pool_obj),
        patch("app.services.comment.emit", new_callable=AsyncMock),
        patch(
            "app.converters.shared.async_resolve_avatar_url",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.repositories.post_repo.find_owner_id", new_callable=AsyncMock, return_value=None
        ),
        patch("app.services.comment.get_redis", return_value=mock_redis),
    ):
        await create_comment(post_id=post_id, user_id=user_id, content="Regular comment")

    # conn.execute should only have comment_count update, NOT answer_count
    execute_calls = conn.execute.call_args_list
    sql_calls = [call[0][0] for call in execute_calls]
    assert not any(
        "answer_count" in sql for sql in sql_calls
    ), f"answer_count should NOT be updated for regular posts, got: {sql_calls}"


# --- B2: Service functions no longer accept pool parameter ---


@pytest.mark.asyncio
async def test_mark_best_answer_no_pool_parameter():
    """B2: mark_best_answer works without pool parameter."""
    import inspect

    from app.services.qa import mark_best_answer

    sig = inspect.signature(mark_best_answer)
    param_names = list(sig.parameters.keys())
    assert "pool" not in param_names, "pool parameter should have been removed"
    assert param_names[0] == "post_id", "First parameter should be post_id"


@pytest.mark.asyncio
async def test_unmark_best_answer_no_pool_parameter():
    """B2: unmark_best_answer works without pool parameter."""
    import inspect

    from app.services.qa import unmark_best_answer

    sig = inspect.signature(unmark_best_answer)
    param_names = list(sig.parameters.keys())
    assert "pool" not in param_names, "pool parameter should have been removed"
    assert param_names[0] == "post_id", "First parameter should be post_id"


@pytest.mark.asyncio
async def test_vote_on_answer_no_pool_parameter():
    """B2: vote_on_answer works without pool parameter."""
    import inspect

    from app.services.qa import vote_on_answer

    sig = inspect.signature(vote_on_answer)
    param_names = list(sig.parameters.keys())
    assert "pool" not in param_names, "pool parameter should have been removed"
    assert param_names[0] == "comment_id", "First parameter should be comment_id"


@pytest.mark.asyncio
async def test_get_user_votes_no_pool_parameter():
    """B2: get_user_votes works without pool parameter."""
    import inspect

    from app.services.qa import get_user_votes

    sig = inspect.signature(get_user_votes)
    param_names = list(sig.parameters.keys())
    assert "pool" not in param_names, "pool parameter should have been removed"
    assert param_names[0] == "post_id", "First parameter should be post_id"


# --- B3: MarkBestAnswerRequest UUID validation ---


def test_mark_best_answer_request_valid_uuid():
    """B3: MarkBestAnswerRequest accepts a valid UUID string."""
    from app.schemas.qa import MarkBestAnswerRequest

    uid = uuid.uuid4()
    req = MarkBestAnswerRequest(comment_id=str(uid))
    assert req.comment_id == uid


def test_mark_best_answer_request_invalid_uuid():
    """B3: MarkBestAnswerRequest rejects an invalid UUID string with ValidationError."""
    from pydantic import ValidationError as PydanticValidationError

    from app.schemas.qa import MarkBestAnswerRequest

    with pytest.raises(PydanticValidationError):
        MarkBestAnswerRequest(comment_id="not-a-uuid")


def test_mark_best_answer_request_empty_string():
    """B3: MarkBestAnswerRequest rejects an empty string."""
    from pydantic import ValidationError as PydanticValidationError

    from app.schemas.qa import MarkBestAnswerRequest

    with pytest.raises(PydanticValidationError):
        MarkBestAnswerRequest(comment_id="")


@pytest.mark.asyncio
async def test_mark_best_answer_comment_id_is_uuid_type():
    """B3: mark_best_answer accepts uuid.UUID for comment_id parameter."""
    import inspect

    from app.services.qa import mark_best_answer

    sig = inspect.signature(mark_best_answer)
    assert sig.parameters["comment_id"].annotation is uuid.UUID


# --- B6: unmark_best_answer post type verification ---


@pytest.mark.asyncio
async def test_unmark_best_answer_not_question():
    """B6: unmark_best_answer rejects non-question posts with 400."""
    from app.services.qa import unmark_best_answer

    post_id = uuid.uuid4()
    user_id = str(uuid.uuid4())

    post_row = {
        "id": post_id,
        "user_id": uuid.UUID(user_id),
        "type": "post",
        "best_answer_id": uuid.uuid4(),
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
            await unmark_best_answer(post_id, user_id)
        assert exc_info.value.status_code == 400
        assert "QA_003" in str(exc_info.value.detail)
        assert "not a question" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_unmark_best_answer_discussion_type_rejected():
    """B6: unmark_best_answer rejects 'discussion' type posts."""
    from app.services.qa import unmark_best_answer

    post_id = uuid.uuid4()
    user_id = str(uuid.uuid4())

    post_row = {
        "id": post_id,
        "user_id": uuid.UUID(user_id),
        "type": "discussion",
        "best_answer_id": uuid.uuid4(),
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
            await unmark_best_answer(post_id, user_id)
        assert exc_info.value.status_code == 400


# --- B7: vote_on_answer error code ---


@pytest.mark.asyncio
async def test_vote_on_non_question_uses_qa_004():
    """B7: Voting on non-question answer uses QA_004 error code, not SYS_422."""
    from app.services.qa import vote_on_answer

    comment_id = uuid.uuid4()
    user_id = str(uuid.uuid4())

    comment_row = {
        "id": comment_id,
        "user_id": uuid.uuid4(),
        "post_id": uuid.uuid4(),
        "post_type": "post",
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
    ):
        with pytest.raises(AppError) as exc_info:
            await vote_on_answer(comment_id, user_id, 1)
        assert exc_info.value.status_code == 400
        assert "QA_004" in str(exc_info.value.detail)
        assert "SYS_422" not in str(exc_info.value.detail)
