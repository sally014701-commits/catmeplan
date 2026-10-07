from datetime import date
import json

from app.database import connect


PROFILE_ID = "default"


def _ensure_profile(connection) -> None:
    exists = connection.execute(
        "SELECT 1 FROM profile WHERE id = ?", (PROFILE_ID,)
    ).fetchone()
    if exists is None:
        connection.execute(
            "INSERT INTO profile (id, color, accessories, started_at) VALUES (?, ?, ?, ?)",
            (PROFILE_ID, "original", "[]", date.today().isoformat()),
        )


def get_profile() -> dict:
    with connect() as connection:
        _ensure_profile(connection)
        row = connection.execute(
            "SELECT color, accessories, started_at FROM profile WHERE id = ?",
            (PROFILE_ID,),
        ).fetchone()
    started_at = date.fromisoformat(row["started_at"])
    return {
        "color": row["color"],
        "accessories": json.loads(row["accessories"]),
        "days_together": (date.today() - started_at).days,
    }


def update_profile(
    color: str | None = None,
    accessories: list[str] | None = None,
) -> dict:
    updates = {}
    if color is not None:
        updates["color"] = color
    if accessories is not None:
        updates["accessories"] = json.dumps(accessories, ensure_ascii=False)

    with connect() as connection:
        _ensure_profile(connection)
        if updates:
            assignments = ", ".join(f"{field} = ?" for field in updates)
            connection.execute(
                f"UPDATE profile SET {assignments} WHERE id = ?",
                (*updates.values(), PROFILE_ID),
            )

    return get_profile()
