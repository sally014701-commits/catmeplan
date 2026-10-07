from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from ap_host import make_host
from backend.app.integrations import google_calendar
from backend.app.services import task_service


router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/connect", response_class=RedirectResponse)
def connect_calendar() -> RedirectResponse:
    return RedirectResponse(url=google_calendar.get_authorization_url())


@router.get("/callback")
def calendar_callback(
    request: Request,
    code: str | None = None,
    error: str | None = None,
) -> dict[str, str]:
    if error or not code:
        raise HTTPException(
            status_code=400,
            detail="Google Calendar authorization was not completed",
        )

    try:
        token = google_calendar.exchange_code_for_token(code)
        host = make_host(request)
        google_calendar.save_token(host, token)
    except Exception as exception:
        raise HTTPException(
            status_code=500,
            detail="Google Calendar connection failed",
        ) from exception

    return {"status": "connected"}


@router.post("/sync")
def sync_calendar(
    request: Request,
    time_min: str | None = None,
    time_max: str | None = None,
) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    start = time_min or now.isoformat()
    end = time_max or (now + timedelta(days=30)).isoformat()
    host = make_host(request)

    try:
        events = google_calendar.fetch_events(host, start, end)
    except RuntimeError as exception:
        raise HTTPException(status_code=400, detail=str(exception)) from exception

    created = 0
    for event in events:
        _, was_created = task_service.process_event(event, return_created=True)
        created += int(was_created)

    return {
        "synced": len(events),
        "created": created,
        "skipped": len(events) - created,
    }
