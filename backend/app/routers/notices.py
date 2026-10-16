from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.notice_agent import import_notice
from app.services.message_service import add_message


router = APIRouter(prefix="/api/notices", tags=["notices"])


class NoticeImportRequest(BaseModel):
    request: str = Field(min_length=1)


@router.post("/import")
def post_notice_import(payload: NoticeImportRequest) -> dict:
    try:
        result = import_notice(payload.request)
    except ValueError as exception:
        raise HTTPException(status_code=422, detail=str(exception)) from exception
    titles = ", ".join(f"'{task['title']}'" for task in result["tasks"])
    goal = f" ({result['project']['goal']})" if result["project"]["goal"] else ""
    add_message(
        role="mallang",
        text=f"공지 '{result['notice']['title']}'을 읽고 {result['project']['name']}{goal} 프로젝트에 {titles} 할 일을 넣어뒀어.",
        task_ids=[task["id"] for task in result["tasks"]],
    )
    return result
