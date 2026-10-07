from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1)
    goal_id: str | None = None
    people: list[str] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    goal_id: str | None = None
    people: list[str] | None = None


class ProjectRecord(BaseModel):
    id: str
    name: str
    goal_id: str | None
    people: list[str]


class ProjectResponse(BaseModel):
    id: str
    name: str
    goal_id: str | None
    people: list[str]
    done_count: int
    total_count: int
