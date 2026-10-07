from fastapi import APIRouter

from app.schemas.message import MessageResponse
from app.services.message_service import list_messages


router = APIRouter(prefix="/api/conversation", tags=["conversation"])


@router.get("", response_model=list[MessageResponse])
def get_conversation() -> list[MessageResponse]:
    return [MessageResponse(**message) for message in list_messages()]
