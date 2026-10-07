from pydantic import BaseModel, Field


class ProfileUpdate(BaseModel):
    color: str | None = None
    accessories: list[str] | None = None


class ProfileResponse(BaseModel):
    color: str
    accessories: list[str]
    days_together: int = Field(ge=0)
