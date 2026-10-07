import os
from pathlib import Path
import tempfile
import unittest

from pydantic import ValidationError

from backend.app.database import initialize_database
from backend.app.schemas.project import ProjectCreate, ProjectRecord, ProjectUpdate
from backend.app.services.project_service import (
    create_project,
    delete_project,
    get_project,
    list_projects,
    update_project,
)


class ProjectSchemaTest(unittest.TestCase):
    def test_project_create_accepts_valid_data(self) -> None:
        project = ProjectCreate(name="IR 준비", people=["에릭"])

        self.assertEqual(project.name, "IR 준비")
        self.assertIsNone(project.goal_id)
        self.assertEqual(project.people, ["에릭"])

    def test_project_create_requires_name(self) -> None:
        with self.assertRaises(ValidationError):
            ProjectCreate()

    def test_project_update_distinguishes_omitted_fields(self) -> None:
        project = ProjectUpdate(name="새 이름")

        self.assertEqual(
            project.model_dump(exclude_unset=True, exclude_none=True),
            {"name": "새 이름"},
        )


class ProjectServiceTest(unittest.TestCase):
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

    def test_crud_flow(self) -> None:
        project_id = create_project("IR 준비", people=["에릭"])

        created = get_project(project_id)
        self.assertEqual(
            created,
            {
                "id": project_id,
                "name": "IR 준비",
                "goal_id": None,
                "people": ["에릭"],
            },
        )
        self.assertEqual(ProjectRecord(**created).id, project_id)

        update = ProjectUpdate(name="IR 발표 준비", people=["에릭", "민지"])
        update_project(
            project_id,
            **update.model_dump(exclude_unset=True, exclude_none=True),
        )

        projects = list_projects()
        self.assertEqual(
            projects,
            [
                {
                    "id": project_id,
                    "name": "IR 발표 준비",
                    "goal_id": None,
                    "people": ["에릭", "민지"],
                }
            ],
        )

        delete_project(project_id)
        self.assertIsNone(get_project(project_id))
        self.assertEqual(list_projects(), [])

    def test_update_missing_project_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "Project not found"):
            update_project("missing-project", name="없는 프로젝트")


if __name__ == "__main__":
    unittest.main()
