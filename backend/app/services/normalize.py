from datetime import date
import uuid

from app.schemas.task import TaskRecord


def normalize_manual(
    content: str,
    due_date: str | None = None,
    duration_min: int | None = None,
    project_id: str | None = None,
    title: str | None = None,
    people: list[str] | None = None,
    external_id: str | None = None,
    source: str = "manual",
) -> TaskRecord:
    """Normalize a manually entered task into the standard task schema."""
    return {
        "id": str(uuid.uuid4()),
        "source": source,
        "content": content,
        "evidence_date": date.today().isoformat(),
        "due_date": due_date,
        "project_id": project_id,
        "title": title,
        "external_id": external_id,
        "people": list(people or []),
        "done": False,
        "duration_min": duration_min,
        "snoozed_count": 0,
    }
