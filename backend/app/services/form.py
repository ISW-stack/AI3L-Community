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


async def get_form_by_id(form_id: uuid.UUID, user_id: str | None = None) -> dict | None:
    row, response_count = await form_repo.find_by_id(form_id)
    if not row:
        return None
    result = row_to_form(row, response_count)
    if user_id is not None:
        has_responded = await form_repo.has_user_responded(form_id, uuid.UUID(user_id))
        result["has_responded"] = has_responded
    return result


async def get_user_response(form_id: uuid.UUID, user_id: str) -> dict | None:
    """Get a specific user's response to a form."""
    response = await form_repo.find_user_response(form_id, uuid.UUID(user_id))
    if not response:
        return None
    answers = response["answers"]
    if isinstance(answers, str):
        answers = json.loads(answers)
    return {
        "id": str(response["id"]),
        "form_id": str(response["form_id"]),
        "user_id": str(response["user_id"]),
        "answers": answers,
        "created_at": response["created_at"].isoformat(),
    }


async def get_form_stats(form_id: uuid.UUID) -> dict:
    """Compute aggregated statistics for all responses to a form."""
    row, _ = await form_repo.find_by_id(form_id)
    if not row:
        raise ValueError("Form not found.")

    questions_raw = row.get("questions")
    if isinstance(questions_raw, str):
        questions = json.loads(questions_raw)
    else:
        questions = questions_raw or []

    responses = await form_repo.find_all_responses(form_id)
    total_responses = len(responses)

    question_stats = []
    for q in questions:
        qid = q["id"]
        qtype = q["type"]
        qlabel = q["label"]
        stats: dict = {}

        if qtype in ("single_choice", "multiple_choice", "dropdown"):
            # Count per option + percentage
            option_counts: dict[str, int] = {}
            option_labels: dict[str, str] = {}
            for opt in q.get("options") or []:
                option_counts[opt["id"]] = 0
                option_labels[opt["id"]] = opt["label"]

            for resp in responses:
                answers = resp.get("answers", {})
                value = answers.get(qid)
                if value is None:
                    continue
                if qtype == "multiple_choice" and isinstance(value, list):
                    for v in value:
                        if v in option_counts:
                            option_counts[v] += 1
                elif isinstance(value, str) and value in option_counts:
                    option_counts[value] += 1

            option_stats = []
            for opt_id, count in option_counts.items():
                pct = (count / total_responses * 100) if total_responses > 0 else 0.0
                option_stats.append(
                    {
                        "option_id": opt_id,
                        "option_label": option_labels.get(opt_id, ""),
                        "count": count,
                        "percentage": round(pct, 1),
                    }
                )
            stats["options"] = option_stats

        elif qtype == "rating":
            values = []
            distribution: dict[int, int] = {}
            for resp in responses:
                answers = resp.get("answers", {})
                value = answers.get(qid)
                if isinstance(value, int) and not isinstance(value, bool):
                    values.append(value)
                    distribution[value] = distribution.get(value, 0) + 1

            if values:
                stats["average"] = round(sum(values) / len(values), 2)
                stats["min"] = min(values)
                stats["max"] = max(values)
            else:
                stats["average"] = 0.0
                stats["min"] = 0
                stats["max"] = 0
            stats["count"] = len(values)
            stats["distribution"] = distribution

        elif qtype in ("text", "textarea"):
            count = 0
            for resp in responses:
                answers = resp.get("answers", {})
                value = answers.get(qid)
                if value is not None and value != "":
                    count += 1
            stats["count"] = count

        elif qtype == "file_upload":
            count = 0
            for resp in responses:
                answers = resp.get("answers", {})
                value = answers.get(qid)
                if value is not None and isinstance(value, dict) and "key" in value:
                    count += 1
            stats["count"] = count

        question_stats.append(
            {
                "question_id": qid,
                "question_type": qtype,
                "question_label": qlabel,
                "stats": stats,
            }
        )

    return {
        "form_id": str(form_id),
        "total_responses": total_responses,
        "question_stats": question_stats,
    }


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

            # Silently drop questions if schema is locked (defense-in-depth)
            if current["is_schema_locked"]:
                questions = None

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

            if await form_repo.check_duplicate_response(form_id, uuid.UUID(user_id), conn):
                raise ValueError("You have already submitted a response to this form.")

            questions = (
                json.loads(form["questions"])
                if isinstance(form["questions"], str)
                else form["questions"]
            )
            _validate_answers(questions, answers)

            # Server-side file size validation (defense-in-depth)
            await _validate_file_sizes(questions, answers)

            response_id = uuid.uuid4()
            inserted = await form_repo.insert_response(
                response_id,
                form_id,
                uuid.UUID(user_id),
                answers,
                conn,
                max_respondents=form["max_respondents"],
            )
            if not inserted:
                raise ValueError("This form has reached its maximum number of responses.")

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
            if isinstance(value, bool) or not isinstance(value, int):
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


async def _validate_file_sizes(questions: list[dict], answers: dict) -> None:
    """Check uploaded file sizes against max_size_mb limits (server-side enforcement)."""
    from app.core.async_storage import get_file_size

    for q in questions:
        if q["type"] != "file_upload":
            continue
        max_size_mb = q.get("max_size_mb")
        if not max_size_mb:
            continue
        value = answers.get(q["id"])
        if not isinstance(value, dict) or "key" not in value:
            continue
        file_size = await get_file_size(value["key"])
        max_bytes = max_size_mb * 1024 * 1024
        if file_size > max_bytes:
            raise ValueError(
                f"File for question '{q['label']}' exceeds the maximum size of {max_size_mb} MB."
            )


async def soft_delete_form(form_id: uuid.UUID, user_id: str, is_admin: bool) -> bool:
    # Permission check and delete happen in the same transaction (via FOR UPDATE
    # in soft_delete_with_permission) to prevent TOCTOU race conditions.
    deleted, banner_url = await form_repo.soft_delete_with_permission(form_id, user_id, is_admin)

    # Best-effort cleanup of form banner from storage
    if deleted and banner_url:
        try:
            from app.core.async_storage import delete_file as async_delete_file

            # banner_url is a storage key like "forms/banners/{form_id}/..."
            # or a proxy URL like "/api/v1/files/content/forms/banners/..."
            key = banner_url
            if key.startswith("/api/v1/files/content/"):
                key = key[len("/api/v1/files/content/") :]
            await async_delete_file(key)
            logger.info(
                "Deleted form banner from storage",
                extra={"form_id": str(form_id), "key": key},
            )
        except Exception:
            logger.warning(
                "Form banner cleanup failed",
                extra={"form_id": str(form_id)},
            )

    return deleted
