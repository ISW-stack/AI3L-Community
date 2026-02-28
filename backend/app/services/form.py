import json
import uuid
from datetime import datetime, timezone

from loguru import logger

from app.core.database import get_pool

_MAX_ACTIVE_FORMS_PER_SIG = 20


def _row_to_form(row: dict, response_count: int = 0) -> dict:
    deadline = row.get("deadline")
    now = datetime.now(timezone.utc)

    is_expired = deadline is not None and deadline < now
    is_full = (
        row.get("max_respondents") is not None
        and response_count >= row["max_respondents"]
    )
    is_active = not is_expired and not is_full and not row.get("is_deleted", False)

    return {
        "id": str(row["id"]),
        "sig_id": str(row["sig_id"]),
        "title": row["title"],
        "description": row.get("description"),
        "banner_url": row.get("banner_url"),
        "deadline": row["deadline"].isoformat() if row.get("deadline") else None,
        "max_respondents": row.get("max_respondents"),
        "questions": (
            json.loads(row["questions"])
            if isinstance(row["questions"], str)
            else row["questions"]
        ),
        "is_schema_locked": row.get("is_schema_locked", False),
        "response_count": response_count,
        "is_active": is_active,
        "created_by": str(row["created_by"]),
        "created_by_name": row.get("creator_display_name") or "Unknown",
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


async def create_form(
    sig_id: str,
    user_id: str,
    title: str,
    description: str | None,
    banner_url: str | None,
    deadline: datetime | None,
    max_respondents: int | None,
    questions: list[dict],
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        # Check active forms limit
        active_count = await conn.fetchval(
            "SELECT COUNT(*) FROM forms WHERE sig_id = $1 AND is_deleted = false",
            uuid.UUID(sig_id),
        )
        if active_count >= _MAX_ACTIVE_FORMS_PER_SIG:
            raise ValueError(
                f"Maximum active forms per SIG ({_MAX_ACTIVE_FORMS_PER_SIG}) reached."
            )

        form_id = uuid.uuid4()
        row = await conn.fetchrow(
            """
            INSERT INTO forms (id, sig_id, created_by, title, description, banner_url,
                               deadline, max_respondents, questions)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
            RETURNING *
            """,
            form_id,
            uuid.UUID(sig_id),
            uuid.UUID(user_id),
            title,
            description,
            banner_url,
            deadline,
            max_respondents,
            json.dumps(questions),
        )
        creator = await conn.fetchrow(
            "SELECT display_name FROM users WHERE id = $1", uuid.UUID(user_id)
        )
        result = dict(row)
        result["creator_display_name"] = (
            creator["display_name"] if creator else "Unknown"
        )
        return _row_to_form(result, 0)


async def get_form_by_id(form_id: uuid.UUID) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT f.*, u.display_name AS creator_display_name
            FROM forms f
            JOIN users u ON u.id = f.created_by
            WHERE f.id = $1 AND f.is_deleted = false
            """,
            form_id,
        )
        if not row:
            return None
        response_count = await conn.fetchval(
            "SELECT COUNT(*) FROM form_responses WHERE form_id = $1", form_id
        )
        return _row_to_form(dict(row), response_count)


async def update_form(
    form_id: uuid.UUID,
    user_id: str,
    is_admin: bool,
    title: str | None = None,
    description: str | None = None,
    banner_url: str | None = None,
    deadline: datetime | None = None,
    max_respondents: int | None = None,
    questions: list[dict] | None = None,
) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        current = await conn.fetchrow(
            "SELECT * FROM forms WHERE id = $1 AND is_deleted = false FOR UPDATE",
            form_id,
        )
        if not current:
            return None

        # Permission check
        if not is_admin and str(current["created_by"]) != user_id:
            raise PermissionError("Only the form creator or admin can update this form.")

        # Reject questions changes if schema is locked
        if questions is not None and current["is_schema_locked"]:
            raise ValueError(
                "Cannot modify questions after responses have been submitted."
            )

        fields = []
        values = []
        idx = 1

        for field_name, value in [
            ("title", title),
            ("description", description),
            ("banner_url", banner_url),
            ("deadline", deadline),
            ("max_respondents", max_respondents),
        ]:
            if value is not None:
                fields.append(f"{field_name} = ${idx}")
                values.append(value)
                idx += 1

        if questions is not None:
            fields.append(f"questions = ${idx}::jsonb")
            values.append(json.dumps(questions))
            idx += 1

        if not fields:
            # Nothing to update, return current
            creator = await conn.fetchrow(
                "SELECT display_name FROM users WHERE id = $1",
                current["created_by"],
            )
            result = dict(current)
            result["creator_display_name"] = (
                creator["display_name"] if creator else "Unknown"
            )
            response_count = await conn.fetchval(
                "SELECT COUNT(*) FROM form_responses WHERE form_id = $1", form_id
            )
            return _row_to_form(result, response_count)

        fields.append("updated_at = NOW()")
        values.append(form_id)
        query = f"""
            UPDATE forms SET {', '.join(fields)}
            WHERE id = ${idx} AND is_deleted = false
            RETURNING *
        """
        row = await conn.fetchrow(query, *values)
        if not row:
            return None

        creator = await conn.fetchrow(
            "SELECT display_name FROM users WHERE id = $1", row["created_by"]
        )
        result = dict(row)
        result["creator_display_name"] = (
            creator["display_name"] if creator else "Unknown"
        )
        response_count = await conn.fetchval(
            "SELECT COUNT(*) FROM form_responses WHERE form_id = $1", form_id
        )
        return _row_to_form(result, response_count)


async def list_forms_by_sig(
    sig_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    pool = get_pool()
    offset = (page - 1) * page_size
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM forms WHERE sig_id = $1 AND is_deleted = false",
            sig_id,
        )
        rows = await conn.fetch(
            """
            SELECT f.*, u.display_name AS creator_display_name
            FROM forms f
            JOIN users u ON u.id = f.created_by
            WHERE f.sig_id = $1 AND f.is_deleted = false
            ORDER BY f.created_at DESC
            LIMIT $2 OFFSET $3
            """,
            sig_id,
            page_size,
            offset,
        )
        forms = []
        for row in rows:
            response_count = await conn.fetchval(
                "SELECT COUNT(*) FROM form_responses WHERE form_id = $1",
                row["id"],
            )
            forms.append(_row_to_form(dict(row), response_count))
        return forms, total


async def submit_response(
    form_id: uuid.UUID, user_id: str, answers: dict
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # 1. Check form exists, not deleted
            form = await conn.fetchrow(
                "SELECT * FROM forms WHERE id = $1 AND is_deleted = false FOR UPDATE",
                form_id,
            )
            if not form:
                raise ValueError("Form not found.")

            # 2. Check not expired
            now = datetime.now(timezone.utc)
            if form["deadline"] and form["deadline"] < now:
                raise ValueError("This form has passed its deadline.")

            # 3. Check not full
            response_count = await conn.fetchval(
                "SELECT COUNT(*) FROM form_responses WHERE form_id = $1", form_id
            )
            if (
                form["max_respondents"] is not None
                and response_count >= form["max_respondents"]
            ):
                raise ValueError("This form has reached its maximum number of responses.")

            # 4. Check duplicate submission
            existing = await conn.fetchval(
                "SELECT id FROM form_responses WHERE form_id = $1 AND user_id = $2",
                form_id,
                uuid.UUID(user_id),
            )
            if existing:
                raise ValueError("You have already submitted a response to this form.")

            # 5. Validate answers against questions
            questions = (
                json.loads(form["questions"])
                if isinstance(form["questions"], str)
                else form["questions"]
            )
            _validate_answers(questions, answers)

            # 6. Insert response
            response_id = uuid.uuid4()
            await conn.execute(
                """
                INSERT INTO form_responses (id, form_id, user_id, answers)
                VALUES ($1, $2, $3, $4::jsonb)
                """,
                response_id,
                form_id,
                uuid.UUID(user_id),
                json.dumps(answers),
            )

            # 7. Lock schema on first response
            if not form["is_schema_locked"]:
                await conn.execute(
                    "UPDATE forms SET is_schema_locked = true, updated_at = NOW() WHERE id = $1",
                    form_id,
                )

            logger.info(
                "Form response submitted",
                extra={"form_id": str(form_id), "user_id": user_id},
            )
            return {"id": str(response_id), "message": "Response submitted successfully."}


def _validate_answers(questions: list[dict], answers: dict) -> None:
    for q in questions:
        qid = q["id"]
        value = answers.get(qid)

        if q.get("required", True) and (value is None or value == "" or value == []):
            raise ValueError(f"Question '{q['label']}' is required.")

        if value is None or value == "" or value == []:
            continue

        qtype = q["type"]

        if qtype in ("text", "textarea"):
            if not isinstance(value, str):
                raise ValueError(
                    f"Question '{q['label']}' expects a text answer."
                )
            max_len = q.get("max_length")
            if max_len and len(value) > max_len:
                raise ValueError(
                    f"Question '{q['label']}' exceeds maximum length of {max_len}."
                )

        elif qtype in ("single_choice", "dropdown"):
            option_ids = {o["id"] for o in (q.get("options") or [])}
            if value not in option_ids:
                raise ValueError(
                    f"Invalid option for question '{q['label']}'."
                )

        elif qtype == "multiple_choice":
            option_ids = {o["id"] for o in (q.get("options") or [])}
            if not isinstance(value, list):
                raise ValueError(
                    f"Question '{q['label']}' expects a list of selected options."
                )
            for v in value:
                if v not in option_ids:
                    raise ValueError(
                        f"Invalid option for question '{q['label']}'."
                    )

        elif qtype == "rating":
            if not isinstance(value, int):
                raise ValueError(
                    f"Question '{q['label']}' expects an integer rating."
                )
            min_val = q.get("min", 1)
            max_val = q.get("max", 5)
            if value < min_val or value > max_val:
                raise ValueError(
                    f"Rating for '{q['label']}' must be between {min_val} and {max_val}."
                )

        elif qtype == "file_upload":
            if not isinstance(value, dict) or "key" not in value or "filename" not in value:
                raise ValueError(
                    f"Question '{q['label']}' expects a file upload with key and filename."
                )
            allowed = q.get("allowed_types")
            if allowed:
                filename = value["filename"]
                ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
                if ext not in [t.lower().lstrip(".") for t in allowed]:
                    raise ValueError(
                        f"File type '.{ext}' is not allowed for question '{q['label']}'."
                    )

    # Check for unknown answer keys
    valid_ids = {q["id"] for q in questions}
    for key in answers:
        if key not in valid_ids:
            raise ValueError(f"Unknown question id: '{key}'.")


async def soft_delete_form(
    form_id: uuid.UUID, user_id: str, is_admin: bool
) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        form = await conn.fetchrow(
            "SELECT created_by FROM forms WHERE id = $1 AND is_deleted = false",
            form_id,
        )
        if not form:
            return False

        if not is_admin and str(form["created_by"]) != user_id:
            raise PermissionError("Only the form creator or admin can delete this form.")

        await conn.execute(
            "UPDATE forms SET is_deleted = true, updated_at = NOW() WHERE id = $1",
            form_id,
        )
        return True
