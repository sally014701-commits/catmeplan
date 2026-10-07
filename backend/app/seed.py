"""One-time sample data so the 말랑이 UI has something to show on first run.

Only runs when the goal table is empty — never touches a database that
already has real data in it.
"""

from datetime import date, datetime, time, timedelta

from app.database import connect
from app.services.goal_service import create_goal
from app.services.project_service import create_project
from app.services.task_service import create_task, snooze_task, update_task


def _at(day: date, hour: int, minute: int = 0) -> str:
    return datetime.combine(day, time(hour, minute)).isoformat()


def seed_sample_data() -> None:
    with connect() as connection:
        has_goals = connection.execute("SELECT 1 FROM goal LIMIT 1").fetchone()
    if has_goals:
        return

    create_goal("여유롭게 사는 사람", is_vision=True)
    health = create_goal(
        "건강", items=["주 2회 필라테스", "아침 스트레칭 습관"]
    )
    career = create_goal(
        "커리어", items=["매일 오전 스탠드업 확인", "이직 정보 주 1회 탐색"]
    )
    life = create_goal("생활")
    create_goal("관계", items=["2주에 한 번 친구 약속"])
    create_goal("자기계발", items=["매주 AI 스터디 참여"])
    create_goal("이직", items=["7/26 이후 진행 없음"], stalled=True)

    lab_project = create_project("떠머기랩", goal_id=career)
    health_project = create_project("건강관리", goal_id=health)
    shopping_project = create_project("쇼핑", goal_id=life)

    today = date.today()
    tomorrow = today + timedelta(days=1)

    create_task(
        "팀 회의 자료 정리",
        due_date=_at(tomorrow, 9),
        duration_min=60,
        project_id=lab_project,
        title="팀 회의 자료 정리",
    )
    create_task(
        "스탠드업 미팅",
        due_date=_at(tomorrow, 10),
        duration_min=30,
        project_id=lab_project,
        title="스탠드업 미팅",
        external_id="seed-standup",
        source="google_calendar",
    )
    create_task(
        "병원 예약 전화",
        due_date=_at(today, 15),
        project_id=health_project,
        title="병원 예약 전화",
    )
    create_task(
        "장보기 — 우유, 사과",
        due_date=_at(today, 19),
        project_id=shopping_project,
        title="장보기 — 우유, 사과",
    )

    tax_task = create_task("세금 서류 정리", due_date=today.isoformat())
    for _ in range(3):
        snooze_task(tax_task["id"])

    exercise_task = create_task("운동 30분", due_date=today.isoformat())
    for _ in range(2):
        snooze_task(exercise_task["id"])

    report_task = create_task(
        "주간 보고서 제출",
        due_date=(today - timedelta(days=2)).isoformat(),
        project_id=lab_project,
        title="주간 보고서 제출",
    )
    update_task(report_task["id"], done=True)

    pilates_task = create_task(
        "필라테스 수업",
        due_date=(today - timedelta(days=1)).isoformat(),
        project_id=health_project,
        title="필라테스 수업",
    )
    update_task(pilates_task["id"], done=True)
