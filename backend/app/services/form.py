import json
import uuid
from datetime import datetime, timezone

from loguru import logger

from app.converters.form_converter import row_to_form
from app.core.blacklist import get_blocked_user_ids
from app.core.constants import (
    DEFAULT_PAGE_SIZE_STANDALONE_FORMS,
    MAX_ACTIVE_FORMS_PER_SIG,
    MAX_ACTIVE_STANDALONE_FORMS_PER_USER,
)
from app.core.database import get_pool
from app.core.errors import AppError, ErrorCode, FormDeadlineError
from app.core.redis import get_redis
from app.repositories import form_repo

_VALID_QUESTION_TYPES = frozenset(
    {"single_choice", "multiple_choice", "rating", "text", "textarea", "dropdown", "file_upload"}
)


def validate_question_schema(questions: list[dict]) -> None:
    """Validate the structure of form questions before saving to JSONB.

    Each question must have "id", "type", and "label" fields.
    The "type" must be one of the recognized question types.
    Choice/dropdown types must include an "options" field.

    Raises ValueError with a descriptive message on validation failure.
    """
    if not isinstance(questions, list):
        raise ValueError("Questions must be a list.")

    seen_ids: set[str] = set()
    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            raise ValueError(f"Question at index {i} must be an object.")

        for required_field in ("id", "type", "label"):
            if required_field not in q:
                raise ValueError(
                    f"Question at index {i} is missing required field '{required_field}'."
                )

        qid = q["id"]
        if qid in seen_ids:
            raise ValueError(f"Duplicate question id '{qid}' at index {i}.")
        seen_ids.add(qid)

        qtype = q["type"]
        if qtype not in _VALID_QUESTION_TYPES:
            raise ValueError(
                f"Question '{qid}' has invalid type '{qtype}'. "
                f"Must be one of: {', '.join(sorted(_VALID_QUESTION_TYPES))}."
            )

        if qtype in ("single_choice", "multiple_choice", "dropdown"):
            if "options" not in q or not isinstance(q["options"], list):
                raise ValueError(f"Question '{qid}' of type '{qtype}' must have an 'options' list.")
            if not q["options"]:
                raise ValueError(
                    f"Question '{qid}' of type '{qtype}' must have at least one option."
                )
            seen_option_ids: set[str] = set()
            for opt_idx, opt in enumerate(q["options"]):
                opt_id = opt.get("id", "")
                if opt_id in seen_option_ids:
                    raise ValueError(
                        f"Question '{qid}' has duplicate option id '{opt_id}' at option index {opt_idx}."
                    )
                seen_option_ids.add(opt_id)


async def create_form(
    sig_id: str | None,
    user_id: str,
    title: str,
    description: str | None,
    banner_url: str | None,
    deadline: datetime | None,
    max_respondents: int | None,
    questions: list[dict],
    allow_non_members: bool = False,
) -> dict:
    validate_question_schema(questions)

    if deadline and deadline < datetime.now(timezone.utc):
        raise FormDeadlineError()

    form_id = uuid.uuid4()
    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            if sig_id is None:
                # Standalone form — enforce per-user limit atomically
                active_count = await form_repo.count_active_standalone_by_user(
                    conn, uuid.UUID(user_id)
                )
                if active_count >= MAX_ACTIVE_STANDALONE_FORMS_PER_USER:
                    raise ValueError(
                        f"Maximum active standalone forms per user "
                        f"({MAX_ACTIVE_STANDALONE_FORMS_PER_USER}) reached."
                    )
                # Standalone forms are always open to all authenticated users
                allow_non_members = True
            else:
                active_count = await form_repo.count_active_in_conn(conn, uuid.UUID(sig_id))
                if active_count >= MAX_ACTIVE_FORMS_PER_SIG:
                    raise ValueError(
                        f"Maximum active forms per SIG ({MAX_ACTIVE_FORMS_PER_SIG}) reached."
                    )

            result = await form_repo.insert_in_conn(
                conn,
                form_id,
                uuid.UUID(sig_id) if sig_id else None,
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


def _normalize_percentages(option_stats: list[dict]) -> None:
    """Normalize rounded percentages so they sum to exactly 100% (or 0%).

    Uses largest-remainder method: round down all percentages, then distribute
    the remaining difference to items with the largest fractional parts.
    """
    if not option_stats:
        return
    total_pct = sum(s["percentage"] for s in option_stats)
    if total_pct == 0.0:
        return

    # Compute exact percentages and floor values
    exact = [s["percentage"] for s in option_stats]
    floored = [int(p * 10) / 10.0 for p in exact]  # floor to 1 decimal
    # Actually, recompute: floor each to 1 decimal
    import math

    floored = [math.floor(p * 10) / 10.0 for p in exact]
    remainders = [(exact[i] - floored[i], i) for i in range(len(exact))]
    floored_sum = round(sum(floored), 1)
    target = 100.0
    diff = round(target - floored_sum, 1)

    # Sort by remainder descending, distribute 0.1 increments
    remainders.sort(key=lambda x: x[0], reverse=True)
    steps = int(round(diff * 10))
    for k in range(min(steps, len(remainders))):
        idx = remainders[k][1]
        floored[idx] = round(floored[idx] + 0.1, 1)

    for i, s in enumerate(option_stats):
        s["percentage"] = floored[i]


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

    total_responses = await form_repo.count_total_responses(form_id)

    # Build per-question accumulators for single-pass streaming aggregation
    q_meta: list[dict] = []  # question metadata
    option_counts_map: dict[str, dict[str, int]] = {}
    option_labels_map: dict[str, dict[str, str]] = {}
    rating_sums: dict[str, int] = {}
    rating_counts: dict[str, int] = {}
    rating_mins: dict[str, int | None] = {}
    rating_maxs: dict[str, int | None] = {}
    rating_dists: dict[str, dict[int, int]] = {}
    text_counts: dict[str, int] = {}
    file_counts: dict[str, int] = {}

    for q in questions:
        qid = q["id"]
        qtype = q["type"]
        qm_entry: dict = {"id": qid, "type": qtype, "label": q["label"]}
        if qtype == "rating":
            qm_entry["range_min"] = q.get("min") if q.get("min") is not None else 1
            qm_entry["range_max"] = q.get("max") if q.get("max") is not None else 5
        q_meta.append(qm_entry)

        if qtype in ("single_choice", "multiple_choice", "dropdown"):
            oc: dict[str, int] = {}
            ol: dict[str, str] = {}
            for opt in q.get("options") or []:
                oc[opt["id"]] = 0
                ol[opt["id"]] = opt["label"]
            option_counts_map[qid] = oc
            option_labels_map[qid] = ol
        elif qtype == "rating":
            rating_sums[qid] = 0
            rating_counts[qid] = 0
            rating_mins[qid] = None
            rating_maxs[qid] = None
            rating_dists[qid] = {}
        elif qtype in ("text", "textarea"):
            text_counts[qid] = 0
        elif qtype == "file_upload":
            file_counts[qid] = 0

    # Stream responses — only one batch in memory at a time
    async for resp in form_repo.iter_responses_batched(form_id):
        answers = resp.get("answers", {})
        for qm in q_meta:
            qid = qm["id"]
            qtype = qm["type"]
            value = answers.get(qid)
            if value is None:
                continue

            if qtype in ("single_choice", "multiple_choice", "dropdown"):
                oc = option_counts_map[qid]
                if qtype == "multiple_choice" and isinstance(value, list):
                    for v in value:
                        if v in oc:
                            oc[v] += 1
                elif isinstance(value, str) and value in oc:
                    oc[value] += 1

            elif qtype == "rating":
                if isinstance(value, int) and not isinstance(value, bool):
                    q_min = qm.get("range_min", 1)
                    q_max = qm.get("range_max", 5)
                    if value < q_min or value > q_max:
                        logger.warning(
                            "Rating value %d out of range [%d, %d] for question %s in form %s",
                            value, q_min, q_max, qid, str(form_id),
                        )
                        continue
                    rating_sums[qid] += value
                    rating_counts[qid] += 1
                    if rating_mins[qid] is None or value < rating_mins[qid]:
                        rating_mins[qid] = value
                    if rating_maxs[qid] is None or value > rating_maxs[qid]:
                        rating_maxs[qid] = value
                    rating_dists[qid][value] = rating_dists[qid].get(value, 0) + 1
                elif value is not None:
                    logger.warning(
                        "Malformed rating value in form response",
                        extra={
                            "form_id": str(form_id),
                            "question_id": qid,
                            "value": repr(value),
                            "value_type": type(value).__name__,
                        },
                    )

            elif qtype in ("text", "textarea"):
                if isinstance(value, str) and value.strip():
                    text_counts[qid] += 1

            elif qtype == "file_upload":
                if isinstance(value, dict) and "key" in value:
                    file_counts[qid] += 1

    # Assemble final stats from accumulators
    question_stats = []
    for qm in q_meta:
        qid = qm["id"]
        qtype = qm["type"]
        stats: dict = {}

        if qtype in ("single_choice", "multiple_choice", "dropdown"):
            option_stats = []
            for opt_id, count in option_counts_map[qid].items():
                pct = (count / total_responses * 100) if total_responses > 0 else 0.0
                option_stats.append(
                    {
                        "option_id": opt_id,
                        "option_label": option_labels_map[qid].get(opt_id, ""),
                        "count": count,
                        "percentage": round(pct, 1),
                    }
                )
            # M-01: Skip normalization for multiple_choice — percentages can
            # legitimately sum to more (or less) than 100% because each
            # respondent selects multiple options.
            if qtype != "multiple_choice":
                _normalize_percentages(option_stats)
            stats["options"] = option_stats

        elif qtype == "rating":
            rc = rating_counts[qid]
            if rc > 0:
                stats["average"] = round(rating_sums[qid] / rc, 2)
                stats["min"] = rating_mins[qid]
                stats["max"] = rating_maxs[qid]
            else:
                stats["average"] = None
                stats["min"] = None
                stats["max"] = None
            stats["count"] = rc
            stats["distribution"] = rating_dists[qid]

        elif qtype in ("text", "textarea"):
            stats["count"] = text_counts[qid]

        elif qtype == "file_upload":
            stats["count"] = file_counts[qid]

        question_stats.append(
            {
                "question_id": qid,
                "question_type": qtype,
                "question_label": qm["label"],
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
    provided_fields: set[str] | None = None,
) -> dict | None:
    pool = get_pool()
    # Fields explicitly provided in the request (allows clearing to None)
    _provided = provided_fields or set()

    async with pool.acquire() as conn:
        async with conn.transaction():
            current = await form_repo.find_for_update(form_id, conn)
            if not current:
                return None

            if not is_admin and str(current["created_by"]) != user_id:
                raise PermissionError("Only the form creator or admin can update this form.")

            # Validate deadline is in the future
            if deadline and deadline < datetime.now(timezone.utc):
                raise FormDeadlineError()

            # Validate max_respondents is not below current response count
            if max_respondents is not None:
                current_count = await form_repo.count_responses(form_id, conn)
                if max_respondents < current_count:
                    raise AppError(
                        ErrorCode.FORM_001,
                        400,
                        f"Cannot set max_respondents below current response count ({current_count}).",
                    )

            # Raise error if schema is locked and questions update is attempted
            if current["is_schema_locked"] and questions is not None:
                raise AppError(
                    ErrorCode.FORM_001, 400, "Cannot modify questions: form schema is locked."
                )

            updates: dict = {}

            for field_name, value in [
                ("title", title),
                ("description", description),
                ("banner_url", banner_url),
                ("deadline", deadline),
                ("max_respondents", max_respondents),
                ("allow_non_members", allow_non_members),
            ]:
                if value is not None:
                    updates[field_name] = value
                elif field_name in _provided:
                    # Field was explicitly set to null — allow clearing
                    updates[field_name] = None

            if questions is not None:
                validate_question_schema(questions)
                updates["questions"] = json.dumps(questions)

            if not updates:
                creator = await conn.fetchrow(
                    "SELECT display_name FROM users WHERE id = $1",
                    current["created_by"],
                )
                result = dict(current)
                result["creator_display_name"] = creator["display_name"] if creator else "Unknown"
                response_count = await form_repo.count_responses(form_id, conn)
                return row_to_form(result, response_count)

            update_result = await form_repo.update(form_id, updates, conn)
            if update_result is None:
                return None
            row, response_count = update_result
            return row_to_form(row, response_count)


async def list_standalone_forms(
    user_id: uuid.UUID,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE_STANDALONE_FORMS,
    q: str | None = None,
) -> tuple[list[dict], int]:
    """List standalone forms owned by user (sig_id IS NULL)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await form_repo.find_standalone(conn, page, page_size, user_id=user_id, q=q)
    if not rows:
        return [], 0
    total = rows[0]["total_count"]
    results = []
    for r in rows:
        d = dict(r)
        response_count = d.pop("response_count", 0)
        results.append(row_to_form(d, response_count))
    return results, total


async def list_forms_by_sig(
    sig_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    results, total = await form_repo.find_by_sig(sig_id, page, page_size)
    return [row_to_form(row, count) for row, count in results], total


async def list_form_responses(
    form_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    viewer_id: str | None = None,
) -> tuple[list[dict], int]:
    exclude: list[uuid.UUID] | None = None
    if viewer_id:
        try:
            redis = get_redis()
            blocked_ids = await get_blocked_user_ids(redis, viewer_id)
            if blocked_ids:
                exclude = [uuid.UUID(uid) for uid in blocked_ids]
        except Exception:
            pass
    results, total = await form_repo.find_responses(
        form_id, page, page_size, exclude_user_ids=exclude
    )
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


async def submit_response(
    form_id: uuid.UUID, user_id: str, answers: dict, is_guest: bool = False
) -> dict:
    # Block check: cannot submit to a form created by a blocked user
    # (guests have no block relationships, skip)
    if not is_guest:
        form_row, _ = await form_repo.find_by_id(form_id)
        if form_row:
            form_creator_id = str(form_row["created_by"])
            if form_creator_id != user_id:
                try:
                    redis = get_redis()
                    blocked_ids = await get_blocked_user_ids(redis, user_id)
                    if form_creator_id in blocked_ids:
                        raise ValueError("Cannot submit this form.")
                except ValueError:
                    raise
                except Exception:
                    pass  # Redis failure → allow submission

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Advisory lock on (form_id, user_id) to prevent TOCTOU race
            # on duplicate response check. Released when transaction completes.
            lock_key = f"{form_id}:{user_id}"
            await conn.execute(
                "SELECT pg_advisory_xact_lock(hashtext($1))",
                lock_key,
            )

            form = await form_repo.find_for_update(form_id, conn)
            if not form:
                raise ValueError("Form not found.")

            # Guests can only submit forms that explicitly allow non-members
            if is_guest and not form.get("allow_non_members", False):
                raise PermissionError("Guests cannot submit this form.")

            if form.get("sig_id") and not form.get("allow_non_members", False):
                from app.repositories import sig_repo

                role = await sig_repo.get_member_role_in_conn(
                    form["sig_id"], uuid.UUID(user_id), conn
                )
                if role is None:
                    raise PermissionError("Only SIG members can submit this form.")

            if form.get("is_closed"):
                raise AppError(ErrorCode.FORM_001, 400, "This form is closed.")

            now = datetime.now(timezone.utc)
            if form["deadline"] and form["deadline"] < now:
                raise FormDeadlineError("This form has passed its deadline.")

            # Duplicate check only for authenticated users (guests use IP rate limit)
            if not is_guest:
                if await form_repo.check_duplicate_response(form_id, uuid.UUID(user_id), conn):
                    raise ValueError("You have already submitted a response to this form.")

            questions = (
                json.loads(form["questions"])
                if isinstance(form["questions"], str)
                else form["questions"]
            )
            _validate_answers(questions, answers)

            # Validate file_upload answer ownership (skip for guests — no user_id)
            if not is_guest:
                _validate_file_ownership(questions, answers, user_id)

            # H-01: Scan status, size, and magic byte validation apply to ALL submitters
            await _validate_file_scan_status(questions, answers)
            await _validate_file_sizes(questions, answers)
            await _validate_file_magic_bytes(questions, answers)

            response_id = uuid.uuid4()
            # Guests: user_id=None (no FK row in users table)
            db_user_id = None if is_guest else uuid.UUID(user_id)
            inserted = await form_repo.insert_response(
                response_id,
                form_id,
                db_user_id,
                answers,
                conn,
                max_respondents=form["max_respondents"],
                guest_allowed=form.get("allow_non_members", False),
            )
            if not inserted:
                raise ValueError("This form has reached its maximum number of responses.")

            if not form["is_schema_locked"]:
                await form_repo.lock_schema(form_id, conn)

            logger.info(
                "Form response submitted",
                extra={"form_id": str(form_id), "user_id": user_id, "is_guest": is_guest},
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


def _validate_file_ownership(questions: list[dict], answers: dict, user_id: str) -> None:
    """Verify that file_upload answer keys belong to the submitting user.

    File keys follow the pattern: editor/{user_id}/{filename} or
    forms/{form_id}/{user_id}/{filename}. The user_id segment must
    match the submitting user.
    """
    for q in questions:
        if q["type"] != "file_upload":
            continue
        value = answers.get(q["id"])
        if not isinstance(value, dict) or "key" not in value:
            continue
        key = value["key"]
        parts = key.split("/")
        # C-02 fix: Check user_id ONLY at expected fixed positions.
        # The previous fallback `user_id in parts` was bypassable by
        # embedding the attacker's UUID in the filename segment.
        # editor/{user_id}/{filename} → parts[1]
        # forms/uploads/{form_id}/{user_id}/{filename} → parts[3]
        # forms/{form_id}/{user_id}/{filename} → parts[2]
        owner_found = False
        if len(parts) >= 3 and parts[0] == "editor" and parts[1] == user_id:
            owner_found = True
        elif (
            len(parts) >= 5
            and parts[0] == "forms"
            and parts[1] == "uploads"
            and parts[3] == user_id
        ):
            owner_found = True
        elif len(parts) >= 4 and parts[0] == "forms" and parts[2] == user_id:
            owner_found = True
        if not owner_found:
            raise PermissionError(
                f"File for question '{q['label']}' does not belong to the submitting user."
            )


async def _validate_file_scan_status(questions: list[dict], answers: dict) -> None:
    """Reject file_upload answers referencing files that haven't passed VirusTotal scan."""
    from app.repositories import file_scan_repo

    for q in questions:
        if q["type"] != "file_upload":
            continue
        value = answers.get(q["id"])
        if not isinstance(value, dict) or "key" not in value:
            continue
        if not await file_scan_repo.is_clean(value["key"]):
            raise ValueError(
                f"File for question '{q['label']}' is not yet cleared for submission "
                "(scan pending or failed). Please wait for the scan to complete."
            )


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
        if file_size == 0:
            raise ValueError(
                f"File for question '{q['label']}' was not found or has been deleted."
            )
        max_bytes = max_size_mb * 1024 * 1024
        if file_size > max_bytes:
            raise ValueError(
                f"File for question '{q['label']}' exceeds the maximum size of {max_size_mb} MB."
            )


async def _validate_file_magic_bytes(questions: list[dict], answers: dict) -> None:
    """H-02: Validate magic bytes for form file uploads to prevent type spoofing."""
    from app.core.async_storage import read_file_header
    from app.core.file_validation import get_content_type_from_extension, validate_magic_number

    for q in questions:
        if q["type"] != "file_upload":
            continue
        value = answers.get(q["id"])
        if not isinstance(value, dict) or "key" not in value or "filename" not in value:
            continue
        filename = value["filename"]
        expected_type = get_content_type_from_extension(filename)
        if expected_type is None:
            # Extension not in allowed list — already caught by _validate_answers
            continue
        try:
            header = await read_file_header(value["key"], size=64)
        except Exception:
            raise ValueError(
                f"File for question '{q['label']}' could not be read from storage."
            )
        if not header:
            raise ValueError(
                f"File for question '{q['label']}' not found in storage."
            )
        if not validate_magic_number(header, expected_type):
            raise ValueError(
                f"File for question '{q['label']}' content does not match its extension."
            )


async def soft_delete_form(form_id: uuid.UUID, user_id: str, is_admin: bool) -> bool:
    # Permission check and delete happen in the same transaction (via FOR UPDATE
    # in soft_delete_with_permission) to prevent TOCTOU race conditions.
    deleted, banner_url, file_upload_entries = await form_repo.soft_delete_with_permission(
        form_id, user_id, is_admin
    )

    if deleted:
        # Best-effort cleanup of file_upload answer files from MinIO + refund quota
        if file_upload_entries:
            await _cleanup_form_upload_files(form_id, file_upload_entries)

        # Best-effort cleanup of form banner from storage
        if banner_url:
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


async def _cleanup_form_upload_files(
    form_id: uuid.UUID, file_entries: list[dict]
) -> None:
    """Best-effort cleanup of file_upload answer files from MinIO and refund storage quota."""
    from app.core.async_storage import delete_file as async_delete_file
    from app.core.async_storage import get_file_size
    from app.repositories import user_repo

    for entry in file_entries:
        key = entry["key"]
        resp_user_id = entry["user_id"]
        try:
            file_size = await get_file_size(key)
            await async_delete_file(key)
            if file_size > 0:
                # M-04 Equivalent: Retry storage refund for form uploads
                for attempt in range(3):
                    try:
                        from app.repositories import user_repo
                        await user_repo.decrement_storage_used(
                            uuid.UUID(resp_user_id), file_size
                        )
                        break
                    except Exception:
                        if attempt == 2:
                            logger.error(
                                "Failed to refund storage quota after form upload deletion",
                                extra={
                                    "form_id": str(form_id),
                                    "key": key,
                                    "user_id": resp_user_id,
                                    "compensation_required": True,
                                },
                                exc_info=True,
                            )
                        else:
                            import asyncio
                            await asyncio.sleep(1)
            logger.info(
                "Deleted form upload file and refunded quota",
                extra={
                    "form_id": str(form_id),
                    "key": key,
                    "user_id": resp_user_id,
                    "size": file_size,
                },
            )
        except Exception:
            logger.warning(
                "Failed to cleanup form upload file",
                extra={"form_id": str(form_id), "key": key},
            )
