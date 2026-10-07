import json
from pathlib import Path
import sqlite3

from backend.app.database import connect
from backend.app.schemas.task import TaskRecord
from backend.app.services.normalize import normalize_manual


TASK_COLUMNS = (
    "id, source, content, evidence_date, due_date, project_id, title,"
    " external_id, people, done, duration_min, snoozed_count"
)


def _row_to_task(row) -> TaskRecord:
    return TaskRecord(
        id=row["id"],
        source=row["source"],
        content=row["content"],
        evidence_date=row["evidence_date"],
        due_date=row["due_date"],
        project_id=row["project_id"],
        title=row["title"],
        external_id=row["external_id"],
        people=json.loads(row["people"]),
        done=bool(row["done"]),
        duration_min=row["duration_min"],
        snoozed_count=row["snoozed_count"],
    )


def create_task(
    content: str,
    due_date: str | None = None,
    duration_min: int | None = None,
    project_id: str | None = None,
    title: str | None = None,
    people: list[str] | None = None,
    external_id: str | None = None,
    source: str = "manual",
    *,
    database_path: Path | None = None,
) -> TaskRecord:
    task = normalize_manual(
        content=content,
        due_date=due_date,
        duration_min=duration_min,
        project_id=project_id,
        title=title,
        people=people,
        external_id=external_id,
        source=source,
    )
    with connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO task (
                id, source, content, evidence_date, due_date,
                project_id, title, external_id, people,
                done, duration_min, snoozed_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task["id"],
                task["source"],
                task["content"],
                task["evidence_date"],
                task["due_date"],
                task["project_id"],
                task["title"],
                task["external_id"],
                json.dumps(task["people"], ensure_ascii=False),
                int(task["done"]),
                task["duration_min"],
                task["snoozed_count"],
            ),
        )
    return task


def list_tasks(*, database_path: Path | None = None) -> list[TaskRecord]:
    with connect(database_path) as connection:
        rows = connection.execute(
            f"""
            SELECT {TASK_COLUMNS}
            FROM task
            ORDER BY evidence_date DESC, rowid DESC
            """
        ).fetchall()
    return [_row_to_task(row) for row in rows]


def get_task(
    task_id: str,
    *,
    database_path: Path | None = None,
) -> TaskRecord | None:
    with connect(database_path) as connection:
        row = connection.execute(
            f"""
            SELECT {TASK_COLUMNS}
            FROM task
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()
    return _row_to_task(row) if row else None


def get_task_by_external_id(
    external_id: str,
    *,
    database_path: Path | None = None,
) -> dict | None:
    with connect(database_path) as connection:
        row = connection.execute(
            f"""
            SELECT {TASK_COLUMNS}
            FROM task
            WHERE external_id = ?
            LIMIT 1
            """,
            (external_id,),
        ).fetchone()
    return _row_to_task(row) if row else None


def update_task(
    task_id: str,
    *,
    due_date: str | None = None,
    duration_min: int | None = None,
    project_id: str | None = None,
    title: str | None = None,
    done: bool | None = None,
    database_path: Path | None = None,
) -> TaskRecord:
    fields = {
        "due_date": due_date,
        "duration_min": duration_min,
        "project_id": project_id,
        "title": title,
        "done": int(done) if done is not None else None,
    }
    updates = {key: value for key, value in fields.items() if value is not None}
    if not updates:
        raise ValueError("No fields to update")

    with connect(database_path) as connection:
        assignments = ", ".join(f"{field} = ?" for field in updates)
        cursor = connection.execute(
            f"UPDATE task SET {assignments} WHERE id = ?",
            (*updates.values(), task_id),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Task not found: {task_id}")

    updated = get_task(task_id, database_path=database_path)
    if updated is None:
        raise ValueError(f"Task not found: {task_id}")
    return updated


def snooze_task(task_id: str, *, database_path: Path | None = None) -> TaskRecord:
    with connect(database_path) as connection:
        cursor = connection.execute(
            "UPDATE task SET snoozed_count = snoozed_count + 1 WHERE id = ?",
            (task_id,),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Task not found: {task_id}")

    snoozed = get_task(task_id, database_path=database_path)
    if snoozed is None:
        raise ValueError(f"Task not found: {task_id}")
    return snoozed


def process_event(
    raw_event: dict,
    *,
    database_path: Path | None = None,
    return_created: bool = False,
) -> TaskRecord | tuple[TaskRecord, bool]:
    existing = get_task_by_external_id(
        raw_event["id"], database_path=database_path
    )
    if existing is not None:
        return (existing, False) if return_created else existing

    task = create_task(
        content=raw_event["content"],
        due_date=raw_event.get("due_date"),
        project_id=raw_event.get("project_id"),
        title=raw_event.get("title"),
        people=raw_event.get("people"),
        external_id=raw_event["id"],
        source="google_calendar",
        database_path=database_path,
    )
    return (task, True) if return_created else task


def update_task_project_id(
    task_id: str,
    project_id: str,
    *,
    connection: sqlite3.Connection | None = None,
) -> None:
    if connection is not None:
        cursor = connection.execute(
            "UPDATE task SET project_id = ? WHERE id = ?",
            (project_id, task_id),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Task not found: {task_id}")
        return

    with connect() as own_connection:
        cursor = own_connection.execute(
            "UPDATE task SET project_id = ? WHERE id = ?",
            (project_id, task_id),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Task not found: {task_id}")
