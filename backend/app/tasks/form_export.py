import asyncio
import csv
import io
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
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

        questions = (
            json.loads(form["questions"])
            if isinstance(form["questions"], str)
            else form["questions"]
        )

        # Fetch all responses with user info
        rows = await conn.fetch(
            """
            SELECT fr.id, fr.answers, fr.created_at, u.username, u.display_name
            FROM form_responses fr
            JOIN users u ON u.id = fr.user_id
            WHERE fr.form_id = $1
            ORDER BY fr.created_at ASC
            """,
            uuid.UUID(form_id),
        )

    # Build CSV
    output = io.StringIO()
    question_labels = [q["label"] for q in questions]
    question_ids = [q["id"] for q in questions]

    writer = csv.writer(output)
    writer.writerow(["Response ID", "Username", "Display Name", "Submitted At"] + question_labels)

    for row in rows:
        answers = json.loads(row["answers"]) if isinstance(row["answers"], str) else row["answers"]
        answer_values = []
        for qid in question_ids:
            val = answers.get(qid, "")
            if isinstance(val, list):
                val = "; ".join(str(v) for v in val)
            elif isinstance(val, dict):
                val = val.get("filename", str(val))
            answer_values.append(str(val) if val is not None else "")

        writer.writerow(
            [
                str(row["id"]),
                row["username"],
                row["display_name"],
                row["created_at"].isoformat(),
            ]
            + answer_values
        )

    # Upload CSV to MinIO
    csv_bytes = output.getvalue().encode("utf-8-sig")
    storage_key = generate_form_export_key(form_id, task_id)
    upload_file(csv_bytes, storage_key, "text/csv")

    # Generate presigned URL (24h expiry)
    download_url = generate_presigned_url(storage_key, expires_in=86400)

    logger.info("Form CSV export completed", extra={"form_id": form_id, "rows": len(rows)})
    return {"download_url": download_url}


def _run_async(coro: Any) -> dict:
    """Run an async coroutine from sync Celery task, cross-platform safe."""
    with ThreadPoolExecutor(1) as pool:
        result: dict = pool.submit(asyncio.run, coro).result()
        return result


@celery.task(bind=True, name="tasks.export_form_csv")
def export_form_csv(self: Any, form_id: str) -> dict:
    """Export form responses to CSV. Runs in Celery worker (sync)."""
    return _run_async(_async_export(form_id, self.request.id))
