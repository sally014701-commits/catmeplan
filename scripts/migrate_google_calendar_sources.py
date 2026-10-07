from pathlib import Path
import sqlite3


DATABASE_PATH = Path(__file__).resolve().parents[1] / "backend/focusplan.db"


def migrate(database_path: Path = DATABASE_PATH) -> tuple[int, int]:
    with sqlite3.connect(database_path) as connection:
        before = connection.execute(
            """
            SELECT COUNT(*) FROM task
            WHERE external_id IS NOT NULL AND source = 'manual'
            """
        ).fetchone()[0]
        print(f"rows_to_update={before}")

        cursor = connection.execute(
            """
            UPDATE task SET source = 'google_calendar'
            WHERE external_id IS NOT NULL AND source = 'manual'
            """
        )
        changed = cursor.rowcount
        print(f"rows_updated={changed}")
    return before, changed


if __name__ == "__main__":
    migrate()
