from fastapi import APIRouter, HTTPException, status

from app.agents.project_agent import confirm_match
from app.agents.task_agent import process_message
from app.schemas.task import (
    AnswerResponse,
    AssignmentResult,
    ConfirmProjectRequest,
    ManualTaskCreate,
    MatchedAssignment,
    MessageTaskCreate,
    TaskCreatedResponse,
    TaskResponse,
    TaskUpdate,
)
from app.services.message_service import add_message
from app.services.project_service import create_project
from app.services.task_service import (
    create_task,
    get_task,
    list_tasks,
    snooze_task,
    update_task,
)


def _summarize_created_tasks(results: list[dict]) -> str:
    titles = [item["task"]["title"] or item["task"]["content"] for item in results]
    if len(titles) == 1:
        due_date = results[0]["task"]["due_date"]
        if due_date:
            return f"'{titles[0]}' 할 일을 {due_date}로 넣어뒀어."
        return f"'{titles[0]}' 할 일을 넣어뒀어."
    joined = ", ".join(f"'{title}'" for title in titles)
    return f"{len(titles)}개로 나눠서 정리해뒀어 — {joined}."


router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskResponse])
def get_tasks() -> list[TaskResponse]:
    return [TaskResponse(**task) for task in list_tasks()]


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def post_task(payload: ManualTaskCreate) -> TaskResponse:
    task = create_task(
        content=payload.content,
        due_date=payload.due_date,
        duration_min=payload.duration_min,
        project_id=payload.project_id,
        title=payload.title,
        people=payload.people,
    )
    return TaskResponse(**task)


@router.patch("/{task_id}", response_model=TaskResponse)
def patch_task(task_id: str, payload: TaskUpdate) -> TaskResponse:
    try:
        task = update_task(
            task_id,
            **payload.model_dump(exclude_unset=True, exclude_none=True),
        )
    except ValueError as exception:
        raise HTTPException(status_code=404, detail=str(exception)) from exception
    return TaskResponse(**task)


@router.post("/{task_id}/snooze", response_model=TaskResponse)
def snooze(task_id: str) -> TaskResponse:
    try:
        task = snooze_task(task_id)
    except ValueError as exception:
        raise HTTPException(status_code=404, detail=str(exception)) from exception
    return TaskResponse(**task)


@router.post(
    "/from-message",
    response_model=list[TaskCreatedResponse] | AnswerResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_tasks_from_message(
    payload: MessageTaskCreate,
) -> list[TaskCreatedResponse] | AnswerResponse:
    add_message(role="user", text=payload.text)
    result = process_message(payload.text)
    if isinstance(result, dict):
        add_message(role="mallang", text=result["text"])
        return AnswerResponse(**result)
    add_message(
        role="mallang",
        text=_summarize_created_tasks(result),
        task_ids=[item["task"]["id"] for item in result],
    )
    return [TaskCreatedResponse(**item) for item in result]


@router.post(
    "/{task_id}/confirm-project",
    response_model=AssignmentResult,
    status_code=status.HTTP_201_CREATED,
)
def confirm_task_project(
    task_id: str,
    payload: ConfirmProjectRequest,
) -> MatchedAssignment:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    project_id = create_project(name=payload.name, people=task["people"])
    confirm_match(dict(task), project_id)
    return MatchedAssignment(
        status="matched",
        matched_by="user_confirmed",
        project_id=project_id,
    )
