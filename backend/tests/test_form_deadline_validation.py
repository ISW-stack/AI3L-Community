"""Tests for form deadline validation (M10)."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.errors import FormDeadlineError


@pytest.mark.anyio
async def test_create_form_past_deadline_raises_error(mock_pool, mock_conn):
    """Creating a form with a past deadline raises FormDeadlineError."""
    from app.services.form import create_form

    past = datetime.now(timezone.utc) - timedelta(hours=1)

    with patch("app.services.form.get_pool", return_value=mock_pool):
        with pytest.raises(FormDeadlineError) as exc_info:
            await create_form(
                sig_id=None,
                user_id=str(uuid.uuid4()),
                title="Test Form",
                description=None,
                banner_url=None,
                deadline=past,
                max_respondents=None,
                questions=[{"id": "q1", "type": "text", "label": "Name"}],
            )
        assert exc_info.value.status_code == 400
        assert "FORM_001" in str(exc_info.value.detail)


@pytest.mark.anyio
async def test_create_form_future_deadline_succeeds(mock_pool, mock_conn):
    """Creating a form with a future deadline does not raise FormDeadlineError."""
    from app.services.form import create_form

    future = datetime.now(timezone.utc) + timedelta(days=7)
    form_id = uuid.uuid4()
    user_id = uuid.uuid4()

    fake_row = {
        "id": form_id,
        "sig_id": None,
        "created_by": user_id,
        "title": "Test Form",
        "description": None,
        "banner_url": None,
        "deadline": future,
        "max_respondents": None,
        "questions": '[{"id": "q1", "type": "text", "label": "Name"}]',
        "is_schema_locked": False,
        "allow_non_members": True,
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "creator_display_name": "Tester",
    }

    with (
        patch("app.services.form.get_pool", return_value=mock_pool),
        patch(
            "app.services.form.form_repo.count_active_standalone_by_user",
            new_callable=AsyncMock,
            return_value=0,
        ),
        patch(
            "app.services.form.form_repo.insert_in_conn",
            new_callable=AsyncMock,
            return_value=fake_row,
        ),
    ):
        result = await create_form(
            sig_id=None,
            user_id=str(user_id),
            title="Test Form",
            description=None,
            banner_url=None,
            deadline=future,
            max_respondents=None,
            questions=[{"id": "q1", "type": "text", "label": "Name"}],
        )
        assert result["id"] == str(form_id)
        assert result["title"] == "Test Form"
