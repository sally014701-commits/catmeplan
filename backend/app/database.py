from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
from typing import Iterator


BACKEND_DIR = Path(__file__).resolve().parents[1]
SCHEMA_PATH = BACKEND_DIR / "schema.sql"
# Vercel's deployed function filesystem is read-only outside /tmp; fall back
# there automatically so the app can at least boot (data resets on cold
# start — this is a demo-only stopgap, not real persistence).
DEFAULT_DATABASE_PATH = (
    Path("/tmp/focusplan.db") if os.environ.get("VERCEL") else BACKEND_DIR / "focusplan.db"
)


def database_path() -> Path:
    return Path(os.environ.get("FOCUSPLAN_DATABASE", DEFAULT_DATABASE_PATH))


def connect(path: Path | None = None) -> sqlite3.Connection:
    connection = sqlite3.connect(path or database_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def transaction(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    connection = connect(path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(path: Path | None = None) -> list[str]:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect(path) as connection:
        connection.executescript(schema)
        task_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(task)")
        }
        if "external_id" not in task_columns:
            connection.execute("ALTER TABLE task ADD COLUMN external_id TEXT")
        if "done" not in task_columns:
            connection.execute(
                "ALTER TABLE task ADD COLUMN done INTEGER NOT NULL DEFAULT 0"
            )
        if "duration_min" not in task_columns:
            connection.execute("ALTER TABLE task ADD COLUMN duration_min INTEGER")
        if "snoozed_count" not in task_columns:
            connection.execute(
                "ALTER TABLE task ADD COLUMN snoozed_count INTEGER NOT NULL DEFAULT 0"
            )
        goal_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(goal)")
        }
        if "is_vision" not in goal_columns:
            connection.execute(
                "ALTER TABLE goal ADD COLUMN is_vision INTEGER NOT NULL DEFAULT 0"
            )
        if "items" not in goal_columns:
            connection.execute(
                "ALTER TABLE goal ADD COLUMN items TEXT NOT NULL DEFAULT '[]'"
            )
        if "stalled" not in goal_columns:
            connection.execute(
                "ALTER TABLE goal ADD COLUMN stalled INTEGER NOT NULL DEFAULT 0"
            )
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    return [row["name"] for row in rows]
