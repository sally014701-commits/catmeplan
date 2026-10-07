from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field


class TaskRecord(TypedDict):
    id: str
    source: str
    content: str
    evidence_date: str
    due_date: str | None
    project_id: str | None
    title: str | None
    external_id: str | None
    people: list[str]
    done: bool
    duration_min: int | None
    snoozed_count: int


class ManualTaskCreate(BaseModel):
    content: str = Field(min_length=1)
    due_date: str | None = None
    duration_min: int | None = None
    project_id: str | None = None
    title: str | None = None
    people: list[str] = Field(default_factory=list)


class MessageTaskCreate(BaseModel):
    text: str = Field(min_length=1)


class TaskUpdate(BaseModel):
    due_date: str | None = None
    duration_min: int | None = None
    project_id: str | None = None
    title: str | None = None
    done: bool | None = None


class TaskResponse(BaseModel):
    id: str
    source: str
    content: str
    evidence_date: str
    due_date: str | None
    project_id: str | None
    title: str | None
    people: list[str]
    done: bool
    duration_min: int | None
    snoozed_count: int


class MatchedAssignment(BaseModel):
    status: Literal["matched"]
    matched_by: Literal["rule", "llm_tiebreak", "user_confirmed"]
    project_id: str


class NeedsConfirmAssignment(BaseModel):
    status: Literal["needs_confirm"]
    matched_by: None = None
    suggested_name: str
    reasoning: str | None = None


AssignmentResult = Annotated[
    MatchedAssignment | NeedsConfirmAssignment,
    Field(discriminator="status"),
]


class TaskAssignmentResponse(BaseModel):
    task: TaskResponse
    assignment: AssignmentResult


class TaskCreatedResponse(TaskAssignmentResponse):
    type: Literal["task_created"]


class AnswerResponse(BaseModel):
    type: Literal["answer"]
    text: str


class ConfirmProjectRequest(BaseModel):
    name: str = Field(min_length=1)
