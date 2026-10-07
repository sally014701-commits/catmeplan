from pydantic import BaseModel


class MessageResponse(BaseModel):
    id: str
    role: str
    text: str
    task_ids: list[str]
    created_at: str
