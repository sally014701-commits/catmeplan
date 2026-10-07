import json
import os
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

from app.integrations.google_calendar import (
    exchange_code_for_token,
    fetch_events,
    get_token,
    get_authorization_url,
    save_token,
)


class GetAuthorizationUrlTest(unittest.TestCase):
    def test_builds_readonly_calendar_authorization_url(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "client-id.apps.googleusercontent.com",
                "GOOGLE_REDIRECT_URI": "http://localhost:8001/api/google/callback",
            },
        ):
            parsed = urlparse(get_authorization_url())

        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "accounts.google.com")
        self.assertEqual(parsed.path, "/o/oauth2/v2/auth")
        self.assertEqual(
            parse_qs(parsed.query),
            {
                "client_id": ["client-id.apps.googleusercontent.com"],
                "redirect_uri": ["http://localhost:8001/api/google/callback"],
                "response_type": ["code"],
                "scope": ["https://www.googleapis.com/auth/calendar.readonly"],
                "access_type": ["offline"],
                "prompt": ["consent"],
            },
        )

    def test_requires_google_oauth_configuration(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "GOOGLE_CLIENT_ID"):
                get_authorization_url()


class ExchangeCodeForTokenTest(unittest.TestCase):
    oauth_environment = {
        "GOOGLE_CLIENT_ID": "client-id.apps.googleusercontent.com",
        "GOOGLE_CLIENT_SECRET": "client-secret",
        "GOOGLE_REDIRECT_URI": "http://localhost:8001/api/google/callback",
    }

    @patch("app.integrations.google_calendar.urlopen")
    def test_exchanges_code_and_returns_required_tokens(self, urlopen: MagicMock) -> None:
        response = MagicMock()
        response.read.return_value = (
            b'{"access_token":"access","refresh_token":"refresh","expires_in":3600}'
        )
        urlopen.return_value.__enter__.return_value = response

        with patch.dict(os.environ, self.oauth_environment):
            result = exchange_code_for_token("authorization-code")

        self.assertEqual(
            result,
            {
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_in": 3600,
            },
        )
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://oauth2.googleapis.com/token")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(
            parse_qs(request.data.decode("utf-8")),
            {
                "client_id": ["client-id.apps.googleusercontent.com"],
                "client_secret": ["client-secret"],
                "code": ["authorization-code"],
                "redirect_uri": ["http://localhost:8001/api/google/callback"],
                "grant_type": ["authorization_code"],
            },
        )

    @patch("app.integrations.google_calendar.urlopen")
    def test_rejects_response_without_refresh_token(self, urlopen: MagicMock) -> None:
        response = MagicMock()
        response.read.return_value = b'{"access_token":"access","expires_in":3600}'
        urlopen.return_value.__enter__.return_value = response

        with patch.dict(os.environ, self.oauth_environment):
            with self.assertRaisesRegex(RuntimeError, "refresh_token"):
                exchange_code_for_token("authorization-code")

    @patch("app.integrations.google_calendar.urlopen")
    def test_raises_clear_error_for_http_failure(self, urlopen: MagicMock) -> None:
        urlopen.side_effect = HTTPError(
            "https://oauth2.googleapis.com/token", 400, "Bad Request", {}, None
        )

        with patch.dict(os.environ, self.oauth_environment):
            with self.assertRaisesRegex(RuntimeError, "HTTP 400"):
                exchange_code_for_token("invalid-code")

    @patch("app.integrations.google_calendar.urlopen")
    def test_raises_clear_error_for_network_failure(self, urlopen: MagicMock) -> None:
        urlopen.side_effect = URLError("connection failed")

        with patch.dict(os.environ, self.oauth_environment):
            with self.assertRaisesRegex(RuntimeError, "network request failed"):
                exchange_code_for_token("authorization-code")


class CalendarTokenStorageTest(unittest.TestCase):
    def test_saves_token_with_fixed_upsert_id_without_mutating_input(self) -> None:
        host = MagicMock()
        scope = host.data.return_value
        token = {
            "id": "caller-supplied-id",
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 3600,
        }

        save_token(host, token)

        host.data.assert_called_once_with("calendar_tokens")
        scope.put.assert_called_once_with(
            {
                "id": "google_calendar",
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_in": 3600,
            }
        )
        self.assertEqual(token["id"], "caller-supplied-id")

    def test_returns_google_calendar_token_from_collection(self) -> None:
        host = MagicMock()
        host.data.return_value.list.return_value = [
            {"id": "another-token", "access_token": "other"},
            {"id": "google_calendar", "access_token": "calendar"},
        ]

        result = get_token(host)

        host.data.assert_called_once_with("calendar_tokens")
        self.assertEqual(
            result,
            {"id": "google_calendar", "access_token": "calendar"},
        )

    def test_returns_none_when_google_calendar_token_is_absent(self) -> None:
        host = MagicMock()
        host.data.return_value.list.return_value = [
            {"id": "another-token", "access_token": "other"},
        ]

        self.assertIsNone(get_token(host))


class FetchEventsTest(unittest.TestCase):
    @patch("app.integrations.google_calendar.urlopen")
    def test_fetches_and_normalizes_calendar_events(
        self, urlopen: MagicMock
    ) -> None:
        host = MagicMock()
        host.data.return_value.list.return_value = [
            {"id": "google_calendar", "access_token": "access-token"}
        ]
        response = MagicMock()
        response.read.return_value = json.dumps(
            {
                "items": [
                    {
                        "id": "timed-event",
                        "summary": "팀 회의",
                        "start": {"dateTime": "2026-08-13T10:00:00+09:00"},
                        "attendees": [
                            {"email": "one@example.com"},
                            {"email": "two@example.com"},
                        ],
                    },
                    {
                        "id": "all-day-event",
                        "start": {"date": "2026-08-14"},
                    },
                ]
            }
        ).encode("utf-8")
        urlopen.return_value.__enter__.return_value = response

        events = fetch_events(
            host,
            "2026-08-12T00:00:00+09:00",
            "2026-08-19T00:00:00+09:00",
        )

        self.assertEqual(
            events,
            [
                {
                    "id": "timed-event",
                    "content": "팀 회의",
                    "due_date": "2026-08-13T10:00:00+09:00",
                    "title": "팀 회의",
                    "people": ["one@example.com", "two@example.com"],
                    "project_id": None,
                },
                {
                    "id": "all-day-event",
                    "content": "제목 없음",
                    "due_date": "2026-08-14",
                    "title": "제목 없음",
                    "people": [],
                    "project_id": None,
                },
            ],
        )
        request = urlopen.call_args.args[0]
        parsed = urlparse(request.full_url)
        self.assertEqual(
            f"{parsed.scheme}://{parsed.netloc}{parsed.path}",
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        )
        self.assertEqual(
            parse_qs(parsed.query),
            {
                "timeMin": ["2026-08-12T00:00:00+09:00"],
                "timeMax": ["2026-08-19T00:00:00+09:00"],
                "singleEvents": ["true"],
                "orderBy": ["startTime"],
            },
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer access-token")

    def test_requires_connected_calendar(self) -> None:
        host = MagicMock()
        host.data.return_value.list.return_value = []

        with self.assertRaisesRegex(RuntimeError, "Google Calendar not connected"):
            fetch_events(host, "2026-08-12", "2026-08-19")

    @patch("app.integrations.google_calendar.urlopen")
    def test_refreshes_expired_access_token_and_preserves_refresh_token(
        self, urlopen: MagicMock
    ) -> None:
        host = MagicMock()
        host.data.return_value.list.return_value = [
            {
                "id": "google_calendar",
                "access_token": "expired-access",
                "refresh_token": "stored-refresh",
            }
        ]
        refresh_response = MagicMock()
        refresh_response.read.return_value = (
            b'{"access_token":"new-access","expires_in":3600}'
        )
        events_response = MagicMock()
        events_response.read.return_value = b'{"items":[]}'
        refresh_context = MagicMock()
        refresh_context.__enter__.return_value = refresh_response
        events_context = MagicMock()
        events_context.__enter__.return_value = events_response
        urlopen.side_effect = [
            HTTPError("events", 401, "Unauthorized", {}, None),
            refresh_context,
            events_context,
        ]

        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "client-id",
                "GOOGLE_CLIENT_SECRET": "client-secret",
            },
        ):
            events = fetch_events(host, "2026-08-12", "2026-08-19")

        self.assertEqual(events, [])
        host.data.return_value.put.assert_called_once_with(
            {
                "id": "google_calendar",
                "access_token": "new-access",
                "expires_in": 3600,
                "refresh_token": "stored-refresh",
            }
        )
        refresh_request = urlopen.call_args_list[1].args[0]
        self.assertEqual(refresh_request.full_url, "https://oauth2.googleapis.com/token")
        self.assertEqual(
            parse_qs(refresh_request.data.decode("utf-8")),
            {
                "client_id": ["client-id"],
                "client_secret": ["client-secret"],
                "refresh_token": ["stored-refresh"],
                "grant_type": ["refresh_token"],
            },
        )
        retry_request = urlopen.call_args_list[2].args[0]
        self.assertEqual(retry_request.get_header("Authorization"), "Bearer new-access")

if __name__ == "__main__":
    unittest.main()
