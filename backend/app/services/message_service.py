from datetime import datetime, timezone
import json
import uuid

from app.database import connect


def _row_to_message(row) -> dict:
    return {
        "id": row["id"],
        "role": row["role"],
        "text": row["text"],
        "task_ids": json.loads(row["task_ids"]),
        "created_at": row["created_at"],
    }


def add_message(role: str, text: str, task_ids: list[str] | None = None) -> dict:
    message_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO message (id, role, text, task_ids, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                message_id,
                role,
                text,
                json.dumps(task_ids or [], ensure_ascii=False),
                created_at,
            ),
        )
    return {
        "id": message_id,
        "role": role,
        "text": text,
        "task_ids": task_ids or [],
        "created_at": created_at,
    }


def list_messages() -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT id, role, text, task_ids, created_at FROM message ORDER BY rowid"
        ).fetchall()
    return [_row_to_message(row) for row in rows]
