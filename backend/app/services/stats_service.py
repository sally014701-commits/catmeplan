from datetime import date, timedelta

from app.services.task_service import list_tasks


WEEKDAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"]


def weekly_stats(*, today: date | None = None) -> dict:
    today = today or date.today()
    monday = today - timedelta(days=today.weekday())
    week_dates = [monday + timedelta(days=offset) for offset in range(7)]

    tasks = list_tasks()
    by_date: dict[str, list[dict]] = {day.isoformat(): [] for day in week_dates}
    for task in tasks:
        bucket_date = (task["due_date"] or task["evidence_date"])[:10]
        if bucket_date in by_date:
            by_date[bucket_date].append(task)

    days = [
        {
            "date": day.isoformat(),
            "label": WEEKDAY_LABELS[index],
            "done_count": sum(1 for task in by_date[day.isoformat()] if task["done"]),
            "total_count": len(by_date[day.isoformat()]),
        }
        for index, day in enumerate(week_dates)
    ]

    week_tasks = [task for day in week_dates for task in by_date[day.isoformat()]]
    postponed = sorted(
        (task for task in tasks if task["snoozed_count"] > 0),
        key=lambda task: task["snoozed_count"],
        reverse=True,
    )[:5]

    return {
        "done_count": sum(1 for task in week_tasks if task["done"]),
        "total_count": len(week_tasks),
        "days": days,
        "postponed": [
            {
                "id": task["id"],
                "title": task["title"] or task["content"],
                "snoozed_count": task["snoozed_count"],
            }
            for task in postponed
        ],
    }
