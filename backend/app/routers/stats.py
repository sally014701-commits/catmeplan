from fastapi import APIRouter

from app.schemas.stats import WeeklyStats
from app.services.stats_service import weekly_stats


router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/weekly", response_model=WeeklyStats)
def get_weekly_stats() -> WeeklyStats:
    return WeeklyStats(**weekly_stats())
