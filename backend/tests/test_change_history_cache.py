from datetime import datetime, timezone

import pytest

import analysis.change_history as change_history

SINCE = datetime(2024, 5, 1, tzinfo=timezone.utc)
UNTIL = datetime(2024, 5, 6, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _clear_cache():
    change_history._activity_cache.clear()
    yield
    change_history._activity_cache.clear()


def test_identical_request_is_served_from_cache(monkeypatch):
    fetch_calls = []

    def fake_fetch(access_token, spreadsheet_id, since, until=None):
        fetch_calls.append(spreadsheet_id)
        return {"activities": []}

    monkeypatch.setattr(change_history, "fetch_change_activity", fake_fetch)

    first = change_history.fetch_change_activity_cached("token-a", "sheet-1", SINCE, UNTIL)
    second = change_history.fetch_change_activity_cached("token-a", "sheet-1", SINCE, UNTIL)

    assert first == {"activities": []}
    assert second == {"activities": []}
    assert fetch_calls == ["sheet-1"]


def test_different_window_is_not_cached_together(monkeypatch):
    fetch_calls = []

    def fake_fetch(access_token, spreadsheet_id, since, until=None):
        fetch_calls.append(since)
        return {"activities": [], "since": since.isoformat()}

    monkeypatch.setattr(change_history, "fetch_change_activity", fake_fetch)

    other_since = datetime(2024, 4, 1, tzinfo=timezone.utc)
    change_history.fetch_change_activity_cached("token-a", "sheet-1", SINCE, UNTIL)
    change_history.fetch_change_activity_cached("token-a", "sheet-1", other_since, UNTIL)

    assert len(fetch_calls) == 2


def test_different_tokens_never_share_a_cache_entry(monkeypatch):
    fetch_calls = []

    def fake_fetch(access_token, spreadsheet_id, since, until=None):
        fetch_calls.append(access_token)
        return {"fetched_with": access_token}

    monkeypatch.setattr(change_history, "fetch_change_activity", fake_fetch)

    result_a = change_history.fetch_change_activity_cached("token-a", "sheet-1", SINCE, UNTIL)
    result_b = change_history.fetch_change_activity_cached("token-b", "sheet-1", SINCE, UNTIL)

    assert result_a == {"fetched_with": "token-a"}
    assert result_b == {"fetched_with": "token-b"}
    assert fetch_calls == ["token-a", "token-b"]
