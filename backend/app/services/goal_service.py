import json
import uuid

from app.database import connect


def _row_to_goal(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "is_vision": bool(row["is_vision"]),
        "items": json.loads(row["items"]),
        "stalled": bool(row["stalled"]),
    }


def create_goal(
    name: str,
    is_vision: bool = False,
    items: list[str] | None = None,
    stalled: bool = False,
) -> str:
    goal_id = str(uuid.uuid4())
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO goal (id, name, is_vision, items, stalled)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                goal_id,
                name,
                int(is_vision),
                json.dumps(items or [], ensure_ascii=False),
                int(stalled),
            ),
        )
    return goal_id


def list_goals() -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT id, name, is_vision, items, stalled FROM goal ORDER BY rowid"
        ).fetchall()
    return [_row_to_goal(row) for row in rows]


def get_goal(goal_id: str) -> dict | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT id, name, is_vision, items, stalled FROM goal WHERE id = ?",
            (goal_id,),
        ).fetchone()
    return _row_to_goal(row) if row else None


def update_goal(goal_id: str, **fields) -> dict:
    allowed_fields = {"name", "items", "stalled"}
    unknown_fields = fields.keys() - allowed_fields
    if unknown_fields:
        names = ", ".join(sorted(unknown_fields))
        raise ValueError(f"Unsupported goal fields: {names}")

    updates = {key: value for key, value in fields.items() if value is not None}
    if "items" in updates:
        updates["items"] = json.dumps(updates["items"], ensure_ascii=False)
    if "stalled" in updates:
        updates["stalled"] = int(updates["stalled"])

    with connect() as connection:
        exists = connection.execute(
            "SELECT 1 FROM goal WHERE id = ?", (goal_id,)
        ).fetchone()
        if exists is None:
            raise ValueError(f"Goal not found: {goal_id}")
        if updates:
            assignments = ", ".join(f"{field} = ?" for field in updates)
            connection.execute(
                f"UPDATE goal SET {assignments} WHERE id = ?",
                (*updates.values(), goal_id),
            )

    updated = get_goal(goal_id)
    if updated is None:
        raise ValueError(f"Goal not found: {goal_id}")
    return updated
