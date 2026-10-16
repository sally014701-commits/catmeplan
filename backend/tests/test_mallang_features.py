from datetime import date, timedelta
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.database import initialize_database
from app.services.goal_service import create_goal, list_goals, update_goal
from app.services.message_service import add_message, list_messages
from app.services.profile_service import get_profile, update_profile
from app.routers.goals import get_goals
from app.services.project_service import create_project, get_project, list_projects
from app.services.stats_service import weekly_stats
from app.services.task_service import (
    create_task,
    list_tasks,
    snooze_task,
    update_task,
)
from app.seed import seed_sample_data


class TemporaryDatabaseTestCase(unittest.TestCase):
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


class GoalServiceTest(TemporaryDatabaseTestCase):
    def test_create_list_update(self) -> None:
        goal_id = create_goal("건강", items=["주 2회 필라테스"])

        goals = list_goals()
        self.assertEqual(
            goals,
            [
                {
                    "id": goal_id,
                    "name": "건강",
                    "is_vision": False,
                    "items": ["주 2회 필라테스"],
                    "stalled": False,
                }
            ],
        )

        updated = update_goal(goal_id, stalled=True)
        self.assertTrue(updated["stalled"])

    def test_update_missing_goal_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "Goal not found"):
            update_goal("missing", stalled=True)


class TaskUpdateSnoozeTest(TemporaryDatabaseTestCase):
    def test_update_toggles_done(self) -> None:
        task = create_task("세금 서류 정리")

        updated = update_task(task["id"], done=True)

        self.assertTrue(updated["done"])
        self.assertEqual(updated["snoozed_count"], 0)

    def test_snooze_increments_count(self) -> None:
        task = create_task("운동 30분")

        snooze_task(task["id"])
        updated = snooze_task(task["id"])

        self.assertEqual(updated["snoozed_count"], 2)

    def test_update_missing_task_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "Task not found"):
            update_task("missing", done=True)


class ProfileServiceTest(TemporaryDatabaseTestCase):
    def test_defaults_then_update(self) -> None:
        profile = get_profile()

        self.assertEqual(profile["color"], "original")
        self.assertEqual(profile["accessories"], [])
        self.assertEqual(profile["days_together"], 0)

        updated = update_profile(color="blue", accessories=["안경"])

        self.assertEqual(updated["color"], "blue")
        self.assertEqual(updated["accessories"], ["안경"])


class MessageServiceTest(TemporaryDatabaseTestCase):
    def test_add_and_list_in_order(self) -> None:
        add_message("user", "내일 회의 준비해야 해")
        add_message("mallang", "넣어뒀어", task_ids=["task-1"])

        messages = list_messages()

        self.assertEqual([message["role"] for message in messages], ["user", "mallang"])
        self.assertEqual(messages[1]["task_ids"], ["task-1"])


class WeeklyStatsTest(TemporaryDatabaseTestCase):
    def test_counts_done_and_total_for_today(self) -> None:
        project_id = create_project("떠머기랩")
        today = date.today()
        done_task = create_task(
            "주간 보고서 제출", due_date=today.isoformat(), project_id=project_id
        )
        update_task(done_task["id"], done=True)
        create_task("팀 회의 자료 정리", due_date=today.isoformat(), project_id=project_id)

        stats = weekly_stats(today=today)

        today_bucket = next(day for day in stats["days"] if day["date"] == today.isoformat())
        self.assertEqual(today_bucket["done_count"], 1)
        self.assertEqual(today_bucket["total_count"], 2)
        self.assertEqual(stats["done_count"], 1)
        self.assertEqual(stats["total_count"], 2)

    def test_postponed_sorted_by_snooze_count(self) -> None:
        light = create_task("운동 30분")
        heavy = create_task("세금 서류 정리")
        snooze_task(light["id"])
        for _ in range(3):
            snooze_task(heavy["id"])

        stats = weekly_stats()

        self.assertEqual(stats["postponed"][0]["id"], heavy["id"])
        self.assertEqual(stats["postponed"][0]["snoozed_count"], 3)


class SeedSampleDataTest(TemporaryDatabaseTestCase):
    def test_seed_is_idempotent_and_populates_tables(self) -> None:
        seed_sample_data()
        seed_sample_data()

        self.assertEqual(
            [goal["name"] for goal in list_goals()],
            ["여유롭게 사는 사람", "이직", "건강", "커리어", "자기계발", "관계", "생활"],
        )
        self.assertEqual(list_tasks(), [])
        self.assertEqual(list_projects(), [])


class GoalsRouterTest(TemporaryDatabaseTestCase):
    def test_items_count_tasks_of_projects_in_goal(self) -> None:
        health = create_goal("건강")
        create_goal("생활")
        project_id = create_project("필라테스", goal_id=health)
        done_task = create_task("필라테스 수업", project_id=project_id)
        update_task(done_task["id"], done=True)
        create_task("필라테스 등록", project_id=project_id)

        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            goals = {goal.name: goal for goal in get_goals()}

        self.assertEqual(goals["건강"].items, ["필라테스 1/2"])
        self.assertEqual(goals["생활"].items, [])

    def test_unassigned_project_is_classified_by_llm(self) -> None:
        create_goal("건강")
        career = create_goal("커리어")
        project_id = create_project("랩 연구")
        create_task("랩 미팅 준비", project_id=project_id)

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test"}), patch(
            "app.agents.project_agent._generate_json",
            return_value={"goal_id": career},
        ):
            goals = {goal.name: goal for goal in get_goals()}

        self.assertEqual(get_project(project_id)["goal_id"], career)
        self.assertEqual(goals["커리어"].items, ["랩 연구 0/1"])

    def test_classification_failure_leaves_project_unassigned(self) -> None:
        create_goal("건강")
        project_id = create_project("랩 연구")

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test"}), patch(
            "app.agents.project_agent._generate_json",
            return_value={"goal_id": "not-a-goal"},
        ):
            get_goals()

        self.assertIsNone(get_project(project_id)["goal_id"])


if __name__ == "__main__":
    unittest.main()
