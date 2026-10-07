from pydantic import BaseModel


class DayStat(BaseModel):
    date: str
    label: str
    done_count: int
    total_count: int


class PostponedTask(BaseModel):
    id: str
    title: str
    snoozed_count: int


class WeeklyStats(BaseModel):
    done_count: int
    total_count: int
    days: list[DayStat]
    postponed: list[PostponedTask]
