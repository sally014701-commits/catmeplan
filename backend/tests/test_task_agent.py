from datetime import date
import json
import logging
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from google.genai import errors

from app.agents.task_agent import (
    answer_query,
    decompose,
    parse_llm_json,
    process_message,
)
from app.database import initialize_database
from app.schemas.task import TaskResponse
from app.services.task_service import list_tasks


class ParseLlmJsonTest(unittest.TestCase):
    def test_parses_markdown_json_code_block(self) -> None:
        raw = '```json\n[{"content": "보고서 작성"}]\n```'

        self.assertEqual(parse_llm_json(raw), [{"content": "보고서 작성"}])

    def test_logs_raw_response_when_json_is_invalid(self) -> None:
        raw = "not valid json"

        with self.assertLogs(
            "app.agents.task_agent", level=logging.ERROR
        ) as logs:
            with self.assertRaises(json.JSONDecodeError):
                parse_llm_json(raw)

        self.assertIn(raw, "\n".join(logs.output))


class DecomposeTest(unittest.TestCase):
    @patch("app.agents.task_agent.genai.Client")
    def test_uses_gemini_model_and_today_in_prompt(self, client_class: Mock) -> None:
        client = client_class.return_value
        client.models.generate_content.return_value.text = (
            '{"intent":"task","tasks":[{"content":"내일까지 보고서 작성",'
            '"title":"보고서 작성","due_date":"2026-07-16","people":[]}]}'
        )

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            result = decompose("내일까지 보고서 작성")

        call = client.models.generate_content.call_args
        self.assertEqual(call.kwargs["model"], "gemini-3.5-flash")
        self.assertIn(date.today().isoformat(), call.kwargs["contents"])
        self.assertEqual(result["intent"], "task")
        self.assertEqual(result["tasks"][0]["content"], "내일까지 보고서 작성")
        self.assertIn("정보를 물어보는 질문인지 판단", call.kwargs["contents"])
        client.close.assert_called_once_with()

    @patch("app.agents.task_agent.genai.Client")
    def test_falls_back_when_requested_model_is_unavailable(
        self, client_class: Mock
    ) -> None:
        client = client_class.return_value
        fallback_response = Mock(
            text='{"intent":"task","tasks":[{"content":"회의 준비",'
            '"title":"회의 준비","due_date":null,"people":[]}]}'
        )
        client.models.generate_content.side_effect = [
            errors.ClientError(404, {"error": {"message": "unavailable"}}),
            fallback_response,
        ]

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            result = decompose("회의 준비")

        models = [
            call.kwargs["model"]
            for call in client.models.generate_content.call_args_list
        ]
        self.assertEqual(models, ["gemini-3.5-flash", "gemini-3.1-flash-lite"])
        self.assertEqual(result["tasks"][0]["content"], "회의 준비")

    @patch("app.agents.task_agent.genai.Client")
    def test_falls_back_when_model_is_temporarily_overloaded(
        self, client_class: Mock
    ) -> None:
        client = client_class.return_value
        final_response = Mock(
            text='{"intent":"task","tasks":[{"content":"자료 정리",'
            '"title":"자료 정리","due_date":null,"people":[]}]}'
        )
        client.models.generate_content.side_effect = [
            errors.ServerError(503, {"error": {"message": "high demand"}}),
            final_response,
        ]

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            result = decompose("자료 정리")

        models = [
            call.kwargs["model"]
            for call in client.models.generate_content.call_args_list
        ]
        self.assertEqual(
            models,
            ["gemini-3.5-flash", "gemini-3.1-flash-lite"],
        )
        self.assertEqual(result["tasks"][0]["content"], "자료 정리")

    @patch("app.agents.task_agent.genai.Client")
    def test_falls_back_when_model_quota_is_exhausted(
        self, client_class: Mock
    ) -> None:
        client = client_class.return_value
        fallback_response = Mock(
            text='{"intent":"task","tasks":[{"content":"필라테스 등록",'
            '"title":"필라테스 등록","due_date":null,"people":[]}]}'
        )
        client.models.generate_content.side_effect = [
            errors.ClientError(429, {"error": {"message": "quota exhausted"}}),
            fallback_response,
        ]

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            result = decompose("필라테스 등록")

        models = [
            call.kwargs["model"]
            for call in client.models.generate_content.call_args_list
        ]
        self.assertEqual(models, ["gemini-3.5-flash", "gemini-3.1-flash-lite"])
        self.assertEqual(result["tasks"][0]["content"], "필라테스 등록")

    @patch("app.agents.task_agent.genai.Client")
    def test_returns_query_intent_with_empty_tasks(self, client_class: Mock) -> None:
        client = client_class.return_value
        client.models.generate_content.return_value.text = (
            '{"intent":"query","tasks":[]}'
        )

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            result = decompose("현재 등록된 할 일이 뭐야?")

        self.assertEqual(result, {"intent": "query", "tasks": []})


class ProcessMessageTest(unittest.TestCase):
    @patch("app.agents.project_agent.assign_project")
    @patch("app.agents.task_agent.decompose")
    def test_persists_multiple_tasks_and_returns_database_rows(
        self,
        decompose_mock: Mock,
        assign_project_mock: Mock,
    ) -> None:
        decompose_mock.return_value = {
            "intent": "task",
            "tasks": [{
                "content": "민수와 보고서 작성",
                "title": "보고서 작성",
                "due_date": "2026-07-16",
                "people": ["민수"],
            },
            {
                "content": "회의실 예약",
                "title": "회의실 예약",
                "due_date": None,
                "people": [],
            }],
        }
        assign_project_mock.side_effect = lambda task: {
            "status": "needs_confirm",
            "suggested_name": f"{task['title']} 프로젝트",
            "task_id": task["id"],
        }
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "focusplan.db"
            initialize_database(database_path)
            with patch.dict(
                os.environ, {"FOCUSPLAN_DATABASE": str(database_path)}
            ):
                result = process_message("민수와 보고서 작성하고 회의실 예약")
                database_tasks = list_tasks(database_path=database_path)

        self.assertEqual(
            {item["task"]["id"]: item["task"] for item in result},
            {task["id"]: task for task in database_tasks},
        )
        self.assertEqual(len(result), 2)
        self.assertTrue(
            all(item["task"]["project_id"] is None for item in result)
        )
        self.assertTrue(
            all(item["assignment"]["status"] == "needs_confirm" for item in result)
        )
        self.assertTrue(all(item["type"] == "task_created" for item in result))

    @patch("app.agents.task_agent.answer_query")
    @patch("app.agents.task_agent.decompose")
    def test_routes_query_intent_to_answer_query(
        self, decompose_mock: Mock, answer_query_mock: Mock
    ) -> None:
        decompose_mock.return_value = {"intent": "query", "tasks": []}
        answer_query_mock.return_value = "등록된 할 일입니다."
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "focusplan.db"
            initialize_database(database_path)
            with patch.dict(
                os.environ, {"FOCUSPLAN_DATABASE": str(database_path)}
            ):
                result = process_message("현재 등록된 할 일이 뭐야?")

        self.assertEqual(
            result, {"type": "answer", "text": "등록된 할 일입니다."}
        )
        answer_query_mock.assert_called_once_with("현재 등록된 할 일이 뭐야?", [])


class AnswerQueryTest(unittest.TestCase):
    @patch("app.agents.task_agent.genai.Client")
    def test_answers_once_using_only_supplied_task_fields(
        self, client_class: Mock
    ) -> None:
        client = client_class.return_value
        client.models.generate_content.return_value.text = "민수와 보고서 작성이 있습니다."
        tasks = [
            {
                "id": "hidden-id",
                "content": "민수와 보고서 작성",
                "title": "보고서 작성",
                "due_date": "2026-08-15",
                "source": "manual",
                "people": ["민수"],
                "external_id": "hidden-external-id",
            }
        ]

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            result = answer_query("민수와 관련된 할 일이 뭐야?", tasks)

        self.assertEqual(result, "민수와 보고서 작성이 있습니다.")
        client.models.generate_content.assert_called_once()
        call = client.models.generate_content.call_args
        self.assertIn("민수와 보고서 작성", call.kwargs["contents"])
        self.assertNotIn("hidden-id", call.kwargs["contents"])
        self.assertNotIn("hidden-external-id", call.kwargs["contents"])
        self.assertIn(
            "해당하는 할 일이 없습니다",
            call.kwargs["config"].system_instruction,
        )
        self.assertIn(
            "source == 'google_calendar'",
            call.kwargs["config"].system_instruction,
        )
        client.close.assert_called_once_with()

    @patch("app.agents.task_agent.genai.Client")
    def test_falls_back_when_answer_model_is_unavailable(
        self, client_class: Mock
    ) -> None:
        client = client_class.return_value
        client.models.generate_content.side_effect = [
            errors.ClientError(404, {"error": {"message": "unavailable"}}),
            Mock(text="대체 모델의 답변"),
        ]

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            result = answer_query("할 일이 뭐야?", [])

        self.assertEqual(result, "대체 모델의 답변")
        self.assertEqual(
            [
                call.kwargs["model"]
                for call in client.models.generate_content.call_args_list
            ],
            ["gemini-3.5-flash", "gemini-3.1-flash-lite"],
        )


class TaskResponseTest(unittest.TestCase):
    def test_serializes_fields_in_database_column_order(self) -> None:
        response = TaskResponse(
            id="task-1",
            source="manual",
            content="자료 정리",
            evidence_date="2026-07-15",
            due_date=None,
            project_id=None,
            title="자료 정리",
            people=[],
            done=False,
            duration_min=None,
            snoozed_count=0,
        )

        self.assertEqual(
            list(response.model_dump()),
            [
                "id",
                "source",
                "content",
                "evidence_date",
                "due_date",
                "project_id",
                "title",
                "people",
                "done",
                "duration_min",
                "snoozed_count",
            ],
        )


if __name__ == "__main__":
    unittest.main()
