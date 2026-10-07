from fastapi import APIRouter, HTTPException, status

from app.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.project_service import (
    create_project,
    delete_project,
    get_project,
    list_projects,
    update_project,
)
from app.services.task_service import list_tasks


router = APIRouter(prefix="/api/projects", tags=["projects"])


def _with_counts(project: dict, tasks_by_project: dict[str, list[dict]]) -> dict:
    tasks = tasks_by_project.get(project["id"], [])
    return {
        **project,
        "done_count": sum(1 for task in tasks if task["done"]),
        "total_count": len(tasks),
    }


def _group_tasks_by_project() -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for task in list_tasks():
        if task["project_id"] is None:
            continue
        grouped.setdefault(task["project_id"], []).append(task)
    return grouped


@router.get("", response_model=list[ProjectResponse])
def get_projects() -> list[ProjectResponse]:
    tasks_by_project = _group_tasks_by_project()
    return [
        ProjectResponse(**_with_counts(project, tasks_by_project))
        for project in list_projects()
    ]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def post_project(payload: ProjectCreate) -> ProjectResponse:
    project_id = create_project(
        name=payload.name,
        goal_id=payload.goal_id,
        people=payload.people,
    )
    project = get_project(project_id)
    return ProjectResponse(**_with_counts(project, {}))


@router.patch("/{project_id}", response_model=ProjectResponse)
def patch_project(project_id: str, payload: ProjectUpdate) -> ProjectResponse:
    try:
        update_project(
            project_id,
            **payload.model_dump(exclude_unset=True, exclude_none=True),
        )
    except ValueError as exception:
        raise HTTPException(status_code=404, detail=str(exception)) from exception
    project = get_project(project_id)
    return ProjectResponse(**_with_counts(project, _group_tasks_by_project()))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project(project_id: str) -> None:
    if get_project(project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    delete_project(project_id)
