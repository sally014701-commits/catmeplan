from pydantic import BaseModel, Field


class GoalCreate(BaseModel):
    name: str = Field(min_length=1)
    is_vision: bool = False
    items: list[str] = Field(default_factory=list)
    stalled: bool = False


class GoalUpdate(BaseModel):
    name: str | None = None
    items: list[str] | None = None
    stalled: bool | None = None


class GoalResponse(BaseModel):
    id: str
    name: str
    is_vision: bool
    items: list[str]
    stalled: bool
