from fastapi import APIRouter

from backend.app.schemas.profile import ProfileResponse, ProfileUpdate
from backend.app.services.profile_service import get_profile, update_profile


router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=ProfileResponse)
def get_profile_route() -> ProfileResponse:
    return ProfileResponse(**get_profile())


@router.put("", response_model=ProfileResponse)
def put_profile_route(payload: ProfileUpdate) -> ProfileResponse:
    profile = update_profile(color=payload.color, accessories=payload.accessories)
    return ProfileResponse(**profile)
