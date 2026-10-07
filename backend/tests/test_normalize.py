from datetime import date
import unittest
import uuid

from backend.app.services.normalize import normalize_manual


class NormalizeManualTest(unittest.TestCase):
    def test_normalizes_manual_task(self) -> None:
        task = normalize_manual(
            content="보고서 초안을 금요일까지 작성한다.",
            due_date="2026-07-17",
            title="보고서 초안",
            people=["민수"],
        )

        self.assertEqual(
            set(task),
            {
                "id",
                "source",
                "content",
                "evidence_date",
                "due_date",
                "project_id",
                "title",
                "external_id",
                "people",
                "done",
                "duration_min",
                "snoozed_count",
            },
        )
        self.assertEqual(uuid.UUID(task["id"]).version, 4)
        self.assertEqual(task["source"], "manual")
        self.assertEqual(task["content"], "보고서 초안을 금요일까지 작성한다.")
        self.assertEqual(task["evidence_date"], date.today().isoformat())
        self.assertEqual(task["due_date"], "2026-07-17")
        self.assertIsNone(task["project_id"])
        self.assertEqual(task["title"], "보고서 초안")
        self.assertIsNone(task["external_id"])
        self.assertEqual(task["people"], ["민수"])

    def test_includes_external_id(self) -> None:
        task = normalize_manual(
            content="외부 일정",
            external_id="event-123",
            source="google_calendar",
        )

        self.assertEqual(task["external_id"], "event-123")
        self.assertEqual(task["source"], "google_calendar")

    def test_due_date_defaults_to_none(self) -> None:
        task = normalize_manual(content="회의 안건을 정리한다.")

        self.assertIsNone(task["due_date"])
        self.assertEqual(task["source"], "manual")
        self.assertEqual(task["people"], [])


if __name__ == "__main__":
    unittest.main()
