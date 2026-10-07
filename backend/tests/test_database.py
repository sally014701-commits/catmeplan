from pathlib import Path
import tempfile
import unittest

from backend.app.database import initialize_database
from backend.app.services.task_service import (
    create_task,
    get_task_by_external_id,
    list_tasks,
    process_event,
)


class InitializeDatabaseTest(unittest.TestCase):
    def test_creates_focusplan_tables(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "focusplan.db"

            tables = initialize_database(database_path)

            self.assertEqual(
                tables, ["goal", "message", "profile", "project", "task"]
            )

    def test_persists_and_lists_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "focusplan.db"
            initialize_database(database_path)

            created = create_task(
                content="API 연결 확인",
                title="연결 테스트",
                people=["민수", "지수"],
                database_path=database_path,
            )
            tasks = list_tasks(database_path=database_path)

            self.assertEqual(tasks, [created])

    def test_gets_task_by_external_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "focusplan.db"
            initialize_database(database_path)
            created = create_task(
                "외부 일정",
                external_id="event-123",
                database_path=database_path,
            )

            found = get_task_by_external_id(
                "event-123", database_path=database_path
            )
            missing = get_task_by_external_id(
                "missing", database_path=database_path
            )

            self.assertEqual(found, created)
            self.assertIsNone(missing)

    def test_process_event_does_not_create_duplicate_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "focusplan.db"
            initialize_database(database_path)
            event = {"id": "event-123", "content": "외부 일정"}

            first = process_event(event, database_path=database_path)
            second, created = process_event(
                event, database_path=database_path, return_created=True
            )
            tasks = list_tasks(database_path=database_path)

            self.assertEqual(second, first)
            self.assertFalse(created)
            self.assertEqual(tasks, [first])
            self.assertEqual(first["external_id"], "event-123")
            self.assertEqual(first["source"], "google_calendar")


if __name__ == "__main__":
    unittest.main()
