import csv
import io
import json
import re
import uuid
from typing import Any

from loguru import logger

from app.celery_app import celery
from app.core.config import settings
from app.core.database import get_pool, init_db_pool
from app.core.storage import (
    generate_form_export_key,
    generate_presigned_url,
    init_storage,
    upload_file,
)
from app.tasks.async_runner import run_async as _run_async

_CSV_FORMULA_CHARS = frozenset("=+-@\t\r")


def _sanitize_csv_value(val: str) -> str:
    """Prefix formula-injection characters with apostrophe to prevent Excel DDE attacks."""
    if val and val[0] in _CSV_FORMULA_CHARS:
        return "'" + val
    return val


async def _async_export(form_id: str, task_id: str) -> dict:
    # Ensure DB pool is available (worker may not have it)
    try:
        pool = get_pool()
    except RuntimeError:
        pool = await init_db_pool(settings.DATABASE_URL)

    # Ensure storage is available
    try:
        from app.core.storage import get_storage

        get_storage()
    except RuntimeError:
        init_storage()

    async with pool.acquire() as conn:
        # Fetch form for column headers
        form = await conn.fetchrow(
            "SELECT questions, title FROM forms WHERE id = $1", uuid.UUID(form_id)
        )
        if not form:
            raise ValueError(f"Form {form_id} not found.")

        # Extract values while still inside the connection context to avoid
        # accessing the record after the connection is released (N-B07).
        form_title: str = form["title"] or ""
        questions = (
            json.loads(form["questions"])
            if isinstance(form["questions"], str)
            else form["questions"]
        )

    # Build option lookup for resolving UUIDs to labels
    option_label_map: dict[str, str] = {}
    for q in questions:
        for opt in q.get("options") or []:
            option_label_map[opt["id"]] = opt.get("label", opt["id"])

    # Build CSV in chunks to avoid loading all responses into memory
    output = io.StringIO()
    question_labels = [q["label"] for q in questions]
    question_ids = [q["id"] for q in questions]

    writer = csv.writer(output)
    writer.writerow(
        ["Response ID", "Username", "Display Name", "Submitted At"]
        + [_sanitize_csv_value(label) for label in question_labels]
    )

    _BATCH_SIZE = 1000
    total_rows = 0
    async with pool.acquire() as conn:
        offset = 0
        while True:
            rows = await conn.fetch(
                """
                SELECT fr.id, fr.answers, fr.created_at, u.username, u.display_name
                FROM form_responses fr
                JOIN users u ON u.id = fr.user_id
                WHERE fr.form_id = $1
                ORDER BY fr.created_at ASC
                LIMIT $2 OFFSET $3
                """,
                uuid.UUID(form_id),
                _BATCH_SIZE,
                offset,
            )
            if not rows:
                break

            for row in rows:
                answers = (
                    json.loads(row["answers"])
                    if isinstance(row["answers"], str)
                    else row["answers"]
                )
                answer_values = []
                for qid in question_ids:
                    val = answers.get(qid, "")
                    if isinstance(val, list):
                        val = "; ".join(option_label_map.get(str(v), str(v)) for v in val)
                    elif isinstance(val, str) and val in option_label_map:
                        val = option_label_map[val]
                    elif isinstance(val, dict):
                        val = val.get("filename", str(val))
                    answer_values.append(str(val) if val is not None else "")

                writer.writerow(
                    [
                        str(row["id"]),
                        _sanitize_csv_value(row["username"]),
                        _sanitize_csv_value(row["display_name"]),
                        row["created_at"].isoformat(),
                    ]
                    + [_sanitize_csv_value(v) for v in answer_values]
                )

            total_rows += len(rows)
            if len(rows) < _BATCH_SIZE:
                break
            offset += _BATCH_SIZE

    # Upload CSV to MinIO — avoid holding both StringIO and bytes simultaneously
    csv_text = output.getvalue()
    output.close()  # release StringIO buffer
    csv_bytes = ("\ufeff" + csv_text).encode("utf-8")  # BOM + single encode
    del csv_text  # release string before upload
    storage_key = generate_form_export_key(form_id, task_id)
    upload_file(csv_bytes, storage_key, "text/csv")

    # Build a safe filename from the form title for the browser download prompt
    raw_title = (form_title or "export").strip()
    safe_title = (
        re.sub(r"[^a-zA-Z0-9_\s\-]", "", raw_title).strip().replace(" ", "_")[:80] or "export"
    )
    download_filename = f"{safe_title}.csv"

    # Generate presigned URL (24h expiry)
    download_url = generate_presigned_url(storage_key, expires_in=86400, filename=download_filename)

    logger.info("Form CSV export completed", extra={"form_id": form_id, "rows": total_rows})
    return {"download_url": download_url}


@celery.task(bind=True, name="tasks.export_form_csv", max_retries=2, default_retry_delay=60)
def export_form_csv(self: Any, form_id: str) -> dict:
    """Export form responses to CSV. Runs in Celery worker (sync)."""
    result: dict = _run_async(_async_export(form_id, self.request.id))
    return result
