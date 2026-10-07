import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from backend.app.main import app
from backend.app.routers.calendar import (
    calendar_callback,
    connect_calendar,
    sync_calendar,
)


class CalendarRouterTest(unittest.TestCase):
    @patch(
        "backend.app.routers.calendar.google_calendar.get_authorization_url",
        return_value="https://accounts.google.com/o/oauth2/v2/auth?client_id=test",
    )
    def test_connect_redirects_to_google_authorization_url(
        self,
        get_authorization_url,
    ) -> None:
        response = connect_calendar()

        self.assertEqual(response.status_code, 307)
        self.assertEqual(
            response.headers["location"],
            "https://accounts.google.com/o/oauth2/v2/auth?client_id=test",
        )
        get_authorization_url.assert_called_once_with()

    def test_calendar_connect_route_is_registered(self) -> None:
        paths = app.openapi()["paths"]

        self.assertIn("get", paths["/api/calendar/connect"])
        self.assertIn("get", paths["/api/calendar/callback"])
        self.assertIn("post", paths["/api/calendar/sync"])

    @patch("backend.app.routers.calendar.task_service.process_event")
    @patch("backend.app.routers.calendar.google_calendar.fetch_events")
    @patch("backend.app.routers.calendar.make_host")
    def test_syncs_calendar_events_and_returns_statistics(
        self,
        make_host: MagicMock,
        fetch_events: MagicMock,
        process_event: MagicMock,
    ) -> None:
        request = MagicMock()
        events = [
            {"id": "new", "content": "새 일정"},
            {"id": "existing", "content": "기존 일정"},
        ]
        fetch_events.return_value = events
        process_event.side_effect = [({"id": "task-1"}, True), ({"id": "task-2"}, False)]

        result = sync_calendar(
            request,
            time_min="2026-08-12T00:00:00Z",
            time_max="2026-09-11T00:00:00Z",
        )

        self.assertEqual(result, {"synced": 2, "created": 1, "skipped": 1})
        fetch_events.assert_called_once_with(
            make_host.return_value,
            "2026-08-12T00:00:00Z",
            "2026-09-11T00:00:00Z",
        )
        self.assertEqual(process_event.call_count, 2)
        process_event.assert_any_call(events[0], return_created=True)
        process_event.assert_any_call(events[1], return_created=True)

    @patch("backend.app.routers.calendar.google_calendar.fetch_events")
    @patch("backend.app.routers.calendar.make_host")
    def test_sync_returns_400_when_calendar_is_not_connected(
        self, make_host: MagicMock, fetch_events: MagicMock
    ) -> None:
        fetch_events.side_effect = RuntimeError("Google Calendar not connected")

        with self.assertRaises(HTTPException) as caught:
            sync_calendar(MagicMock())

        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(caught.exception.detail, "Google Calendar not connected")

    @patch("backend.app.routers.calendar.google_calendar.save_token")
    @patch("backend.app.routers.calendar.make_host")
    @patch("backend.app.routers.calendar.google_calendar.exchange_code_for_token")
    def test_callback_exchanges_and_saves_token(
        self,
        exchange_code_for_token: MagicMock,
        make_host: MagicMock,
        save_token: MagicMock,
    ) -> None:
        request = MagicMock()
        token = {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 3600,
        }
        exchange_code_for_token.return_value = token
        host = make_host.return_value

        result = calendar_callback(request=request, code="authorization-code")

        self.assertEqual(result, {"status": "connected"})
        exchange_code_for_token.assert_called_once_with("authorization-code")
        make_host.assert_called_once_with(request)
        save_token.assert_called_once_with(host, token)

    def test_callback_returns_400_for_google_error(self) -> None:
        with self.assertRaises(HTTPException) as caught:
            calendar_callback(
                request=MagicMock(),
                error="access_denied",
            )

        self.assertEqual(caught.exception.status_code, 400)
        self.assertNotIn("access_denied", caught.exception.detail)

    def test_callback_returns_400_when_code_is_missing(self) -> None:
        with self.assertRaises(HTTPException) as caught:
            calendar_callback(request=MagicMock())

        self.assertEqual(caught.exception.status_code, 400)

    @patch("backend.app.routers.calendar.google_calendar.exchange_code_for_token")
    def test_callback_hides_token_exchange_error(
        self,
        exchange_code_for_token: MagicMock,
    ) -> None:
        exchange_code_for_token.side_effect = RuntimeError(
            "secret-value access-token-value"
        )

        with self.assertRaises(HTTPException) as caught:
            calendar_callback(request=MagicMock(), code="invalid-code")

        self.assertEqual(caught.exception.status_code, 500)
        self.assertEqual(
            caught.exception.detail,
            "Google Calendar connection failed",
        )
        self.assertNotIn("secret-value", caught.exception.detail)


if __name__ == "__main__":
    unittest.main()
