"""Google Calendar integration boundary."""

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
GOOGLE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_EVENTS_ENDPOINT = (
    "https://www.googleapis.com/calendar/v3/calendars/primary/events"
)
CALENDAR_READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
GOOGLE_CALENDAR_TOKEN_ID = "google_calendar"

load_dotenv(PROJECT_ROOT / ".env")


def get_authorization_url() -> str:
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI")
    if not client_id or not redirect_uri:
        raise RuntimeError(
            "GOOGLE_CLIENT_ID and GOOGLE_REDIRECT_URI must be configured"
        )

    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": CALENDAR_READONLY_SCOPE,
            "access_type": "offline",
            "prompt": "consent",
        }
    )
    return f"{GOOGLE_AUTHORIZATION_ENDPOINT}?{query}"


def exchange_code_for_token(code: str) -> dict:
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI")
    if not client_id or not client_secret or not redirect_uri:
        raise RuntimeError(
            "GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REDIRECT_URI "
            "must be configured"
        )

    body = urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    request = Request(
        GOOGLE_TOKEN_ENDPOINT,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(
            f"Google token exchange failed with HTTP {error.code}"
        ) from error
    except URLError as error:
        raise RuntimeError("Google token exchange network request failed") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("Google token exchange returned an invalid response") from error

    refresh_token = payload.get("refresh_token")
    if not refresh_token:
        raise RuntimeError("Google token response did not include refresh_token")

    return {
        "access_token": payload.get("access_token"),
        "refresh_token": refresh_token,
        "expires_in": payload.get("expires_in"),
    }


def save_token(host, token: dict) -> None:
    host.data("calendar_tokens").put(
        {
            **token,
            "id": GOOGLE_CALENDAR_TOKEN_ID,
        }
    )


def get_token(host) -> dict | None:
    for token in host.data("calendar_tokens").list():
        if token.get("id") == GOOGLE_CALENDAR_TOKEN_ID:
            return token
    return None


def _refresh_token(host, token: dict) -> dict:
    body = urlencode(
        {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "refresh_token": token["refresh_token"],
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    request = Request(
        GOOGLE_TOKEN_ENDPOINT,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        refreshed = json.loads(response.read().decode("utf-8"))

    refreshed["refresh_token"] = (
        refreshed.get("refresh_token") or token["refresh_token"]
    )
    save_token(host, refreshed)
    return refreshed


def _fetch_events_payload(access_token: str, query: str) -> dict:
    request = Request(
        f"{GOOGLE_CALENDAR_EVENTS_ENDPOINT}?{query}",
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_events(host, time_min: str, time_max: str) -> list[dict]:
    token = get_token(host)
    if token is None:
        raise RuntimeError("Google Calendar not connected")

    query = urlencode(
        {
            "timeMin": time_min,
            "timeMax": time_max,
            "singleEvents": "true",
            "orderBy": "startTime",
        }
    )
    try:
        payload = _fetch_events_payload(token["access_token"], query)
    except HTTPError as error:
        if error.code != 401:
            raise RuntimeError(
                f"Google Calendar events request failed with HTTP {error.code}"
            ) from error
        try:
            token = _refresh_token(host, token)
            payload = _fetch_events_payload(token["access_token"], query)
        except HTTPError as retry_error:
            raise RuntimeError(
                f"Google Calendar events request failed with HTTP {retry_error.code}"
            ) from retry_error
        except URLError as retry_error:
            raise RuntimeError(
                "Google Calendar events network request failed"
            ) from retry_error
        except (UnicodeDecodeError, json.JSONDecodeError) as retry_error:
            raise RuntimeError(
                "Google Calendar events returned an invalid response"
            ) from retry_error
    except URLError as error:
        raise RuntimeError("Google Calendar events network request failed") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("Google Calendar events returned an invalid response") from error

    events = []
    for event in payload.get("items", []):
        summary = event.get("summary") or "제목 없음"
        events.append(
            {
                "id": event["id"],
                "content": summary,
                "due_date": event["start"].get("dateTime")
                or event["start"].get("date"),
                "title": summary,
                "people": [
                    attendee["email"] for attendee in event.get("attendees", [])
                ],
                "project_id": None,
            }
        )
    return events
