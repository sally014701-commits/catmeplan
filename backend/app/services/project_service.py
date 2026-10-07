import json
import sqlite3
import uuid

from backend.app.database import connect


def _row_to_project(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "goal_id": row["goal_id"],
        "people": json.loads(row["people"]),
    }


def create_project(
    name: str,
    goal_id: str | None = None,
    people: list[str] | None = None,
) -> str:
    project_id = str(uuid.uuid4())
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO project (id, name, goal_id, people)
            VALUES (?, ?, ?, ?)
            """,
            (
                project_id,
                name,
                goal_id,
                json.dumps(people or [], ensure_ascii=False),
            ),
        )
    return project_id


def list_projects() -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT id, name, goal_id, people FROM project ORDER BY rowid"
        ).fetchall()
    return [_row_to_project(row) for row in rows]


def get_project(project_id: str) -> dict | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT id, name, goal_id, people FROM project WHERE id = ?",
            (project_id,),
        ).fetchone()
    return _row_to_project(row) if row else None


def update_project(
    project_id: str,
    *,
    connection: sqlite3.Connection | None = None,
    **fields,
) -> None:
    allowed_fields = {"name", "goal_id", "people"}
    unknown_fields = fields.keys() - allowed_fields
    if unknown_fields:
        names = ", ".join(sorted(unknown_fields))
        raise ValueError(f"Unsupported project fields: {names}")

    updates = {key: value for key, value in fields.items() if value is not None}
    if "people" in updates:
        updates["people"] = json.dumps(updates["people"], ensure_ascii=False)

    if connection is not None:
        exists = connection.execute(
            "SELECT 1 FROM project WHERE id = ?",
            (project_id,),
        ).fetchone()
        if exists is None:
            raise ValueError(f"Project not found: {project_id}")
        if updates:
            assignments = ", ".join(f"{field} = ?" for field in updates)
            connection.execute(
                f"UPDATE project SET {assignments} WHERE id = ?",
                (*updates.values(), project_id),
            )
        return

    with connect() as own_connection:
        exists = own_connection.execute(
            "SELECT 1 FROM project WHERE id = ?",
            (project_id,),
        ).fetchone()
        if exists is None:
            raise ValueError(f"Project not found: {project_id}")
        if updates:
            assignments = ", ".join(f"{field} = ?" for field in updates)
            own_connection.execute(
                f"UPDATE project SET {assignments} WHERE id = ?",
                (*updates.values(), project_id),
            )


def delete_project(project_id: str) -> None:
    with connect() as connection:
        connection.execute("DELETE FROM project WHERE id = ?", (project_id,))
