from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import initialize_database
from app.routers.calendar import router as calendar_router
from app.routers.conversation import router as conversation_router
from app.routers.goals import router as goals_router
from app.routers.profile import router as profile_router
from app.routers.projects import router as projects_router
from app.routers.stats import router as stats_router
from app.routers.tasks import router as tasks_router
from app.seed import seed_sample_data


def cors_origins() -> list[str]:
    configured = os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000",
    )
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    seed_sample_data()
    yield


app = FastAPI(title="FocusPlan API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(tasks_router)
app.include_router(calendar_router)
app.include_router(projects_router)
app.include_router(goals_router)
app.include_router(stats_router)
app.include_router(profile_router)
app.include_router(conversation_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
