from unittest.mock import MagicMock

import requests

from me_crawler import config
from me_crawler.client import ApiClient


def _client_with_plain_session() -> ApiClient:
    return ApiClient(auth=MagicMock(), session=requests.Session())


def test_single_page(requests_mock):
    requests_mock.get(
        config.TRANSACTIONS_URL,
        json={"transactions": [{"uuid": "a"}, {"uuid": "b"}], "hasMore": False},
    )
    client = _client_with_plain_session()

    result = client.get_transactions(from_date="2026-06-01", to_date="2026-06-12")

    assert [t["uuid"] for t in result] == ["a", "b"]
    assert requests_mock.call_count == 1
    qs = requests_mock.request_history[0].qs
    assert qs["fromdate"] == ["2026-06-01"]
    assert qs["todate"] == ["2026-06-12"]


def test_cursor_pagination_drops_from_date_on_next_pages(requests_mock):
    requests_mock.get(
        config.TRANSACTIONS_URL,
        [
            {
                "json": {
                    "transactions": [{"uuid": "a"}],
                    "hasMore": True,
                    "nextCursorDate": "2026-06-08",
                    "nextCursorId": 123,
                }
            },
            {"json": {"transactions": [{"uuid": "b"}], "hasMore": False}},
        ],
    )
    client = _client_with_plain_session()

    result = client.get_transactions(from_date="2026-06-01", to_date="2026-06-12")

    assert [t["uuid"] for t in result] == ["a", "b"]
    assert requests_mock.call_count == 2

    second = requests_mock.request_history[1].qs
    assert "fromdate" not in second
    assert second["todate"] == ["2026-06-08"]
    assert second["cursorid"] == ["123"]


def test_stops_when_cursor_passes_from_date(requests_mock):
    requests_mock.get(
        config.TRANSACTIONS_URL,
        json={
            "transactions": [{"uuid": "a"}],
            "hasMore": True,
            "nextCursorDate": "2026-05-20",  # anterior ao from_date
            "nextCursorId": 999,
        },
    )
    client = _client_with_plain_session()

    result = client.get_transactions(from_date="2026-06-01", to_date="2026-06-12")

    assert len(result) == 1
    assert requests_mock.call_count == 1


def test_relogin_on_401(requests_mock):
    requests_mock.get(
        config.TRANSACTIONS_URL,
        [
            {"status_code": 401},
            {"json": {"transactions": [{"uuid": "a"}], "hasMore": False}},
        ],
    )
    auth = MagicMock()
    auth.force_login.return_value = requests.Session()
    client = ApiClient(auth=auth, session=requests.Session())

    result = client.get_transactions(to_date="2026-06-12")

    assert [t["uuid"] for t in result] == ["a"]
    auth.force_login.assert_called_once()
    assert requests_mock.call_count == 2
