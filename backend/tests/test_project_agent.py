import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from app.agents.project_agent import (
    _llm_pick_among,
    _llm_propose_new,
    assign_project,
    parse_llm_json_cot,
)
from app.database import initialize_database
from app.services.project_service import create_project, get_project
from app.services.task_service import (
    create_task,
    get_task,
    update_task_project_id,
)


class ProjectAgentRuleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.task = {
            "id": "task-1",
            "content": "에릭과 민지랑 IR 자료 수정",
            "people": ["에릭", "민지"],
        }

    @patch("app.agents.project_agent._confirm_match")
    @patch("app.agents.project_agent.project_service.list_projects")
    def test_assigns_the_only_matching_project(
        self,
        list_projects: MagicMock,
        confirm_match: MagicMock,
    ) -> None:
        list_projects.return_value = [
            {"id": "project-1", "people": ["에릭"]},
            {"id": "project-2", "people": ["수진"]},
        ]
        confirm_match.return_value = {
            "status": "matched",
            "project_id": "project-1",
        }

        result = assign_project(self.task)

        self.assertEqual(
            result,
            {
                "status": "matched",
                "project_id": "project-1",
                "matched_by": "rule",
            },
        )
        confirm_match.assert_called_once_with(self.task, "project-1")

    @patch("app.agents.project_agent._llm_propose_new")
    @patch("app.agents.project_agent.project_service.list_projects")
    def test_no_match_delegates_to_llm_proposal(
        self,
        list_projects: MagicMock,
        propose_new: MagicMock,
    ) -> None:
        list_projects.return_value = [
            {"id": "project-1", "people": ["수진"]},
        ]

        propose_new.return_value = {
            "status": "needs_confirm",
            "suggested_name": "IR 자료 정리",
            "task_id": "task-1",
        }

        self.assertEqual(assign_project(self.task), propose_new.return_value)
        propose_new.assert_called_once_with(self.task)

    @patch("app.agents.project_agent._confirm_match")
    @patch("app.agents.project_agent.project_service.list_projects")
    def test_assigns_project_with_larger_overlap(
        self,
        list_projects: MagicMock,
        confirm_match: MagicMock,
    ) -> None:
        list_projects.return_value = [
            {"id": "project-1", "people": ["에릭"]},
            {"id": "project-2", "people": ["에릭", "민지", "수진"]},
        ]
        confirm_match.return_value = {
            "status": "matched",
            "project_id": "project-2",
        }

        result = assign_project(self.task)

        self.assertEqual(
            result,
            {
                "status": "matched",
                "project_id": "project-2",
                "matched_by": "rule",
            },
        )
        confirm_match.assert_called_once_with(self.task, "project-2")

    @patch("app.agents.project_agent._llm_pick_among")
    @patch("app.agents.project_agent.project_service.list_projects")
    def test_tie_delegates_to_llm_tiebreak(
        self,
        list_projects: MagicMock,
        pick_among: MagicMock,
    ) -> None:
        list_projects.return_value = [
            {"id": "project-1", "people": ["에릭"]},
            {"id": "project-2", "people": ["민지"]},
            {"id": "project-3", "people": ["수진"]},
        ]

        pick_among.return_value = {
            "status": "matched",
            "project_id": "project-2",
            "matched_by": "llm_tiebreak",
        }

        self.assertEqual(assign_project(self.task), pick_among.return_value)
        pick_among.assert_called_once_with(
            self.task,
            ["project-1", "project-2"],
        )

    @patch("app.agents.project_agent._confirm_match")
    @patch("app.agents.project_agent._generate_json")
    @patch("app.agents.project_agent.project_service.get_project")
    def test_llm_tiebreak_confirms_returned_candidate(
        self,
        get_project: MagicMock,
        generate_json: MagicMock,
        confirm_match: MagicMock,
    ) -> None:
        get_project.side_effect = [
            {"id": "project-1", "name": "IR 준비", "people": ["에릭"]},
            {"id": "project-2", "name": "논문", "people": ["민지"]},
        ]
        generate_json.return_value = {"project_id": "project-2"}
        confirm_match.return_value = {
            "status": "matched",
            "project_id": "project-2",
        }

        result = _llm_pick_among(self.task, ["project-1", "project-2"])

        self.assertEqual(
            result,
            {
                "status": "matched",
                "project_id": "project-2",
                "matched_by": "llm_tiebreak",
            },
        )
        confirm_match.assert_called_once_with(self.task, "project-2")


class ParseLlmJsonCotTest(unittest.TestCase):
    def test_parses_last_json_code_block(self) -> None:
        raw = """1단계: 사용자 상황을 추론한다.
```json
{"suggested_name": "첫 제안"}
```
3단계: 최종 이름을 다듬는다.
```json
{"suggested_name": "랩 연구"}
```"""

        self.assertEqual(
            parse_llm_json_cot(raw),
            {"suggested_name": "랩 연구"},
        )

    def test_parses_json_at_end_without_code_block(self) -> None:
        raw = """1단계: 새로운 루틴을 시작하려는 사람이다.
2단계: 반복적인 운동 활동이다.
{"suggested_name": "요가 수업"}"""

        self.assertEqual(
            parse_llm_json_cot(raw),
            {"suggested_name": "요가 수업"},
        )


class ProjectProposalLiveTest(unittest.TestCase):
    @unittest.skipUnless(
        os.environ.get("GEMINI_API_KEY"),
        "GEMINI_API_KEY is required for the live proposal check",
    )
    def test_prints_live_suggestions_for_few_shot_examples(self) -> None:
        tasks = [
            {
                "id": "live-lab",
                "content": "오늘 오후 5시에 있는 랩 연구미팅 준비해야해",
                "people": [],
            },
            {
                "id": "live-yoga",
                "content": "내일은 요가를 새로 등록해서 수업을 갈거야",
                "people": [],
            },
        ]

        for task in tasks:
            result = _llm_propose_new(task)
            print(f"LIVE suggested_name ({task['content']}): {result['suggested_name']}")
            print(f"LIVE reasoning ({task['content']}):\n{result['reasoning']}")
            self.assertIn("1단계", result["reasoning"])
            self.assertIn("2단계", result["reasoning"])
            self.assertIn("3단계", result["reasoning"])


class ProjectAgentTransactionTest(unittest.TestCase):
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

    def test_rolls_back_task_assignment_when_project_update_fails(self) -> None:
        project_id = create_project("IR 준비", people=["에릭"])
        task = create_task("IR 수정", people=["에릭"])

        with patch(
            "app.agents.project_agent.project_service.update_project",
            side_effect=RuntimeError("forced project update failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "forced project update failure"):
                assign_project(task)

        stored_task = get_task(task["id"])
        self.assertIsNotNone(stored_task)
        self.assertIsNone(stored_task["project_id"])
        self.assertEqual(get_project(project_id)["people"], ["에릭"])

    def test_update_task_project_id_rejects_missing_task(self) -> None:
        project_id = create_project("IR 준비")

        with self.assertRaisesRegex(ValueError, "Task not found"):
            update_task_project_id("missing-task", project_id)

    def test_no_match_proposes_project_without_assigning_task(self) -> None:
        task = create_task("새 서비스 소개서 작성", people=[])

        with patch(
            "app.agents.project_agent._llm_propose_new",
            return_value={
                "status": "needs_confirm",
                "suggested_name": "서비스 소개서",
                "task_id": task["id"],
            },
        ):
            result = assign_project(task)

        self.assertEqual(
            result,
            {
                "status": "needs_confirm",
                "suggested_name": "서비스 소개서",
                "task_id": task["id"],
            },
        )
        stored_task = get_task(task["id"])
        self.assertIsNotNone(stored_task)
        self.assertIsNone(stored_task["project_id"])


if __name__ == "__main__":
    unittest.main()
