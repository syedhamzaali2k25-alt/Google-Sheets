import pytest

import app.google_sheets as google_sheets


@pytest.fixture(autouse=True)
def _clear_cache():
    google_sheets._raw_cache.clear()
    yield
    google_sheets._raw_cache.clear()


def test_cache_hit_skips_the_expensive_fetch(monkeypatch):
    fetch_calls = []

    def fake_fetch(access_token, spreadsheet_id):
        fetch_calls.append(spreadsheet_id)
        return {"title": "v1"}

    monkeypatch.setattr(google_sheets, "fetch_spreadsheet_revision", lambda token, sid: "rev-1")
    monkeypatch.setattr(google_sheets, "fetch_spreadsheet_raw", fake_fetch)

    first = google_sheets.fetch_spreadsheet_raw_cached("token-a", "sheet-1")
    second = google_sheets.fetch_spreadsheet_raw_cached("token-a", "sheet-1")

    assert first == {"title": "v1"}
    assert second == {"title": "v1"}
    assert fetch_calls == ["sheet-1"]  # the expensive fetch ran exactly once


def test_changed_revision_invalidates_the_cache(monkeypatch):
    fetch_calls = []
    revisions = iter(["rev-1", "rev-2"])

    def fake_fetch(access_token, spreadsheet_id):
        fetch_calls.append(spreadsheet_id)
        return {"call": len(fetch_calls)}

    monkeypatch.setattr(google_sheets, "fetch_spreadsheet_revision", lambda token, sid: next(revisions))
    monkeypatch.setattr(google_sheets, "fetch_spreadsheet_raw", fake_fetch)

    first = google_sheets.fetch_spreadsheet_raw_cached("token-a", "sheet-1")
    second = google_sheets.fetch_spreadsheet_raw_cached("token-a", "sheet-1")

    assert first == {"call": 1}
    assert second == {"call": 2}  # revision changed -> re-fetched, not stale
    assert len(fetch_calls) == 2


def test_different_tokens_never_share_a_cache_entry(monkeypatch):
    """Security property: even if two different callers ask about the same
    spreadsheet id with the same (hypothetically identical) revision, the
    cache must not let one token's request be served from data fetched
    using a different token — the fingerprint is part of the cache key."""
    fetch_calls = []

    def fake_fetch(access_token, spreadsheet_id):
        fetch_calls.append(access_token)
        return {"fetched_with": access_token}

    monkeypatch.setattr(google_sheets, "fetch_spreadsheet_revision", lambda token, sid: "rev-1")
    monkeypatch.setattr(google_sheets, "fetch_spreadsheet_raw", fake_fetch)

    result_a = google_sheets.fetch_spreadsheet_raw_cached("token-a", "sheet-1")
    result_b = google_sheets.fetch_spreadsheet_raw_cached("token-b", "sheet-1")

    assert result_a == {"fetched_with": "token-a"}
    assert result_b == {"fetched_with": "token-b"}
    assert fetch_calls == ["token-a", "token-b"]  # both were actually fetched, not shared


def test_unverifiable_revision_bypasses_caching_entirely(monkeypatch):
    """If the lightweight revision check fails (e.g. transient error), we
    must not cache — better to pay for an extra fetch than risk serving
    stale or unauthorized data."""
    fetch_calls = []

    def fake_fetch(access_token, spreadsheet_id):
        fetch_calls.append(spreadsheet_id)
        return {"call": len(fetch_calls)}

    monkeypatch.setattr(google_sheets, "fetch_spreadsheet_revision", lambda token, sid: None)
    monkeypatch.setattr(google_sheets, "fetch_spreadsheet_raw", fake_fetch)

    first = google_sheets.fetch_spreadsheet_raw_cached("token-a", "sheet-1")
    second = google_sheets.fetch_spreadsheet_raw_cached("token-a", "sheet-1")

    assert first == {"call": 1}
    assert second == {"call": 2}
    assert len(fetch_calls) == 2  # never cached
