"""One-time goal categories so the 기록 map has something to classify into.

Only runs when the goal table is empty — never touches a database that
already has real data in it. No sample tasks or projects: those come from
the user's own conversation.
"""

from app.database import connect
from app.services.goal_service import create_goal


GOAL_CATEGORIES = ("이직", "건강", "커리어", "자기계발", "관계", "생활")


def seed_sample_data() -> None:
    with connect() as connection:
        has_goals = connection.execute("SELECT 1 FROM goal LIMIT 1").fetchone()
    if has_goals:
        return

    create_goal("여유롭게 사는 사람", is_vision=True)
    for name in GOAL_CATEGORIES:
        create_goal(name)
