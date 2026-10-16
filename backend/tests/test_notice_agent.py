from unittest.mock import patch

from app.agents.notice_agent import import_notice
from app.services.goal_service import create_goal
from app.services.project_service import list_projects
from tests.test_mallang_features import TemporaryDatabaseTestCase


LIST_PAGE = """
<a href="?mode=view&amp;articleNo=1&amp;x=1" title="자세히 보기">
    자원봉사 모집 </a>
<a href="?mode=view&amp;articleNo=140568&amp;x=1" title="자세히 보기">
    [인사캠] 2026년 11월 체력증진센터 회원모집 안내 </a>
"""
VIEW_PAGE = """
<a href="#" data-title="[인사캠] 2026년 11월 체력증진센터 회원모집 안내"></a>
<pre class="pre">Ⅰ. 등록 기준일 - 2026년 11월 1일(일)
 학 생 - 1개월 35,000원</pre>
"""


def fake_fetch(params: dict) -> str:
    return LIST_PAGE if params["mode"] == "list" else VIEW_PAGE


class ImportNoticeTest(TemporaryDatabaseTestCase):
    def test_finds_notice_then_creates_tasks_project_and_category(self) -> None:
        health = create_goal("건강")
        create_goal("생활")
        replies = [
            {"keywords": ["헬스장", "체력증진센터"]},
            {"index": 1},
            {
                "project_name": "헬스",
                "tasks": [
                    {
                        "title": "11월 헬스장 등록",
                        "content": "등록 기준일 - 2026년 11월 1일(일)",
                        "due_date": "2026-11-01",
                    }
                ],
            },
            {"goal_id": health},
        ]
        with patch("app.agents.notice_agent._fetch", side_effect=fake_fetch), patch(
            "app.agents.notice_agent._generate_json", side_effect=replies[:3]
        ), patch("app.agents.project_agent._generate_json", side_effect=replies[3:]):
            result = import_notice("skku 헬스장 2026 11월 안내")

        self.assertEqual(result["notice"]["title"], "[인사캠] 2026년 11월 체력증진센터 회원모집 안내")
        self.assertEqual(result["project"]["name"], "헬스")
        self.assertEqual(result["project"]["goal"], "건강")
        self.assertEqual([task["due_date"] for task in result["tasks"]], ["2026-11-01"])
        self.assertEqual([project["goal_id"] for project in list_projects()], [health])

    def test_rejects_notice_outside_search_results(self) -> None:
        with patch("app.agents.notice_agent._fetch", side_effect=fake_fetch), patch(
            "app.agents.notice_agent._generate_json",
            side_effect=[{"keywords": ["헬스장"]}, {"index": 9}],
        ):
            with self.assertRaisesRegex(ValueError, "outside the search results"):
                import_notice("헬스장")
