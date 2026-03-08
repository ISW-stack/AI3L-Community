import json
import uuid
from datetime import datetime, timezone

from loguru import logger

from app.converters.form_converter import row_to_form
from app.core.constants import MAX_ACTIVE_FORMS_PER_SIG
from app.core.database import get_pool
from app.core.errors import AppError, ErrorCode
from app.repositories import form_repo


async def create_form(
    sig_id: str,
    user_id: str,
    title: str,
    description: str | None,
    banner_url: str | None,
    deadline: datetime | None,
    max_respondents: int | None,
    questions: list[dict],
    allow_non_members: bool = False,
) -> dict:
    active_count = await form_repo.count_active(uuid.UUID(sig_id))
    if active_count >= MAX_ACTIVE_FORMS_PER_SIG:
        raise ValueError(f"Maximum active forms per SIG ({MAX_ACTIVE_FORMS_PER_SIG}) reached.")

    form_id = uuid.uuid4()
    result = await form_repo.insert(
        form_id,
        uuid.UUID(sig_id),
        uuid.UUID(user_id),
        title,
        description,
        banner_url,
        deadline,
        max_respondents,
        questions,
        allow_non_members,
    )
    return row_to_form(result, 0)


async def get_form_by_id(form_id: uuid.UUID) -> dict | None:
    row, response_count = await form_repo.find_by_id(form_id)
    if not row:
        return None
    return row_to_form(row, response_count)


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
    allow_non_members: bool | None = None,
) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            current = await form_repo.find_for_update(form_id, conn)
            if not current:
                return None

            if not is_admin and str(current["created_by"]) != user_id:
                raise PermissionError("Only the form creator or admin can update this form.")

            if questions is not None and current["is_schema_locked"]:
                raise ValueError("Cannot modify questions after responses have been submitted.")

            fields = []
            values = []
            idx = 1

            for field_name, value in [
                ("title", title),
                ("description", description),
                ("banner_url", banner_url),
                ("deadline", deadline),
                ("max_respondents", max_respondents),
                ("allow_non_members", allow_non_members),
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
                creator = await conn.fetchrow(
                    "SELECT display_name FROM users WHERE id = $1",
                    current["created_by"],
                )
                result = dict(current)
                result["creator_display_name"] = creator["display_name"] if creator else "Unknown"
                response_count = await form_repo.count_responses(form_id, conn)
                return row_to_form(result, response_count)

            update_result = await form_repo.update(form_id, fields, values, conn)
            if update_result is None:
                return None
            row, response_count = update_result
            return row_to_form(row, response_count)


async def list_forms_by_sig(
    sig_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    results, total = await form_repo.find_by_sig(sig_id, page, page_size)
    return [row_to_form(row, count) for row, count in results], total


async def list_form_responses(
    form_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    results, total = await form_repo.find_responses(form_id, page, page_size)
    converted = []
    for r in results:
        answers = r["answers"]
        if isinstance(answers, str):
            answers = json.loads(answers)
        converted.append(
            {
                "id": str(r["id"]),
                "form_id": str(r["form_id"]),
                "user_id": str(r["user_id"]),
                "display_name": r["display_name"],
                "username": r["username"],
                "answers": answers,
                "created_at": r["created_at"].isoformat(),
            }
        )
    return converted, total


async def submit_response(form_id: uuid.UUID, user_id: str, answers: dict) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            form = await form_repo.find_for_update(form_id, conn)
            if not form:
                raise ValueError("Form not found.")

            if not form.get("allow_non_members", False):
                from app.repositories import sig_repo

                role = await sig_repo.get_member_role_in_conn(
                    form["sig_id"], uuid.UUID(user_id), conn
                )
                if role is None:
                    raise PermissionError("Only SIG members can submit this form.")

            now = datetime.now(timezone.utc)
            if form["deadline"] and form["deadline"] < now:
                raise AppError(ErrorCode.FORM_001, 400, "This form has passed its deadline.")

            response_count = await form_repo.count_responses(form_id, conn)
            if form["max_respondents"] is not None and response_count >= form["max_respondents"]:
                raise ValueError("This form has reached its maximum number of responses.")

            if await form_repo.check_duplicate_response(form_id, uuid.UUID(user_id), conn):
                raise ValueError("You have already submitted a response to this form.")

            questions = (
                json.loads(form["questions"])
                if isinstance(form["questions"], str)
                else form["questions"]
            )
            _validate_answers(questions, answers)

            response_id = uuid.uuid4()
            await form_repo.insert_response(response_id, form_id, uuid.UUID(user_id), answers, conn)

            if not form["is_schema_locked"]:
                await form_repo.lock_schema(form_id, conn)

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
                raise ValueError(f"Question '{q['label']}' expects a text answer.")
            max_len = q.get("max_length")
            if max_len and len(value) > max_len:
                raise ValueError(f"Question '{q['label']}' exceeds maximum length of {max_len}.")

        elif qtype in ("single_choice", "dropdown"):
            option_ids = {o["id"] for o in (q.get("options") or [])}
            if value not in option_ids:
                raise ValueError(f"Invalid option for question '{q['label']}'.")

        elif qtype == "multiple_choice":
            option_ids = {o["id"] for o in (q.get("options") or [])}
            if not isinstance(value, list):
                raise ValueError(f"Question '{q['label']}' expects a list of selected options.")
            for v in value:
                if v not in option_ids:
                    raise ValueError(f"Invalid option for question '{q['label']}'.")

        elif qtype == "rating":
            if not isinstance(value, int):
                raise ValueError(f"Question '{q['label']}' expects an integer rating.")
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

    valid_ids = {q["id"] for q in questions}
    for key in answers:
        if key not in valid_ids:
            raise ValueError(f"Unknown question id: '{key}'.")


async def soft_delete_form(form_id: uuid.UUID, user_id: str, is_admin: bool) -> bool:
    # Check permission before deleting
    row, _ = await form_repo.find_by_id(form_id)
    if not row:
        return False
    if not is_admin and str(row["created_by"]) != user_id:
        raise PermissionError("Only the form creator or admin can delete this form.")
    deleted, _ = await form_repo.soft_delete(form_id)
    return deleted
