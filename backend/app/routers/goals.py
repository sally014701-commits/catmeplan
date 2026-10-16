import logging
import os

from fastapi import APIRouter, HTTPException, status

from app.agents.project_agent import classify_project_goal
from app.schemas.goal import GoalCreate, GoalResponse, GoalUpdate
from app.services.goal_service import create_goal, list_goals, update_goal
from app.services.project_service import list_projects
from app.services.task_service import list_tasks


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/goals", tags=["goals"])


def _classify_unassigned_projects() -> None:
    if not os.environ.get("GEMINI_API_KEY"):
        return
    for project in list_projects():
        if project["goal_id"] is not None:
            continue
        try:
            classify_project_goal(project)
        except Exception:
            logger.exception("Could not classify project %s", project["id"])


def _project_items(goal_id: str, projects: list[dict], tasks: list[dict]) -> list[str]:
    items = []
    for project in projects:
        if project["goal_id"] != goal_id:
            continue
        project_tasks = [task for task in tasks if task["project_id"] == project["id"]]
        done = sum(1 for task in project_tasks if task["done"])
        items.append(f"{project['name']} {done}/{len(project_tasks)}")
    return items


@router.get("", response_model=list[GoalResponse])
def get_goals() -> list[GoalResponse]:
    _classify_unassigned_projects()
    projects = list_projects()
    tasks = list_tasks()
    return [
        GoalResponse(**{**goal, "items": _project_items(goal["id"], projects, tasks)})
        for goal in list_goals()
    ]


@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def post_goal(payload: GoalCreate) -> GoalResponse:
    goal_id = create_goal(
        name=payload.name,
        is_vision=payload.is_vision,
        items=payload.items,
        stalled=payload.stalled,
    )
    return GoalResponse(**{**payload.model_dump(), "id": goal_id})


@router.patch("/{goal_id}", response_model=GoalResponse)
def patch_goal(goal_id: str, payload: GoalUpdate) -> GoalResponse:
    try:
        goal = update_goal(
            goal_id,
            **payload.model_dump(exclude_unset=True, exclude_none=True),
        )
    except ValueError as exception:
        raise HTTPException(status_code=404, detail=str(exception)) from exception
    return GoalResponse(**goal)
