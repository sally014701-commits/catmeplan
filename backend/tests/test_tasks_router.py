import os
from pathlib import Path
import tempfile
import unittest

from backend.app.database import initialize_database
from backend.app.routers.tasks import confirm_task_project
from backend.app.schemas.task import ConfirmProjectRequest
from backend.app.services.project_service import get_project
from backend.app.services.task_service import create_task, get_task


class ConfirmTaskProjectTest(unittest.TestCase):
    def setUp(self) -> None:
        self._database_setting = os.environ.get("FOCUSPLAN_DATABASE")
        self._temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self._temporary_directory.name) / "focusplan.db"
        os.environ["FOCUSPLAN_DATABASE"] = str(database_path)
        initialize_database(database_path)

    def tearDown(self) -> None:
        if self._database_setting is None:
            os.environ.pop("FOCUSPLAN_DATABASE", None)
        else:
            os.environ["FOCUSPLAN_DATABASE"] = self._database_setting
        self._temporary_directory.cleanup()

    def test_creates_and_assigns_user_confirmed_project(self) -> None:
        task = create_task("에릭과 IR 수정", people=["에릭"])

        result = confirm_task_project(
            task["id"],
            ConfirmProjectRequest(name="IR 준비"),
        )

        self.assertEqual(result.status, "matched")
        self.assertEqual(result.matched_by, "user_confirmed")
        self.assertIsNotNone(result.project_id)
        stored_task = get_task(task["id"])
        self.assertEqual(stored_task["project_id"], result.project_id)
        project = get_project(result.project_id)
        self.assertEqual(project["name"], "IR 준비")
        self.assertEqual(project["people"], ["에릭"])


if __name__ == "__main__":
    unittest.main()
