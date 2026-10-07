from fastapi import APIRouter, HTTPException, status

from app.schemas.goal import GoalCreate, GoalResponse, GoalUpdate
from app.services.goal_service import create_goal, list_goals, update_goal


router = APIRouter(prefix="/api/goals", tags=["goals"])


@router.get("", response_model=list[GoalResponse])
def get_goals() -> list[GoalResponse]:
    return [GoalResponse(**goal) for goal in list_goals()]


@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def post_goal(payload: GoalCreate) -> GoalResponse:
    goal_id = create_goal(
        name=payload.name,
        is_vision=payload.is_vision,
        items=payload.items,
        stalled=payload.stalled,
    )
    return GoalResponse(**{**payload.model_dump(), "id": goal_id})


@router.patch("/{goal_id}", response_model=GoalResponse)
def patch_goal(goal_id: str, payload: GoalUpdate) -> GoalResponse:
    try:
        goal = update_goal(
            goal_id,
            **payload.model_dump(exclude_unset=True, exclude_none=True),
        )
    except ValueError as exception:
        raise HTTPException(status_code=404, detail=str(exception)) from exception
    return GoalResponse(**goal)
