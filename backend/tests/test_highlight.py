import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main_module
from analysis.health_score import Category, Finding, Severity, compute_health_report
from analysis.highlight import (
    CLEAR_COLOR,
    HIGHLIGHT_COLOR,
    build_clear_requests,
    build_highlight_requests,
    count_affected_cells,
)
from analysis.structure import build_spreadsheet_structure
from app.db import get_db
from app.models import AppliedHighlight, Base
from app.repository import get_or_create_user, upsert_applied_highlight

SALES_FIXTURE = Path(__file__).parent / "fixtures" / "sales_sheet_raw.json"


@pytest.fixture
def sales_raw() -> dict:
    return json.loads(SALES_FIXTURE.read_text())


@pytest.fixture
def sales_structure(sales_raw):
    return build_spreadsheet_structure(sales_raw)


@pytest.fixture
def sales_health(sales_structure, sales_raw):
    return compute_health_report(sales_structure, sales_raw)


# ---------------------------------------------------------------------------
# build_highlight_requests / build_clear_requests / count_affected_cells
# ---------------------------------------------------------------------------


def test_build_highlight_requests_produces_correct_grid_ranges(sales_structure, sales_health):
    duplicate_finding = next(f for f in sales_health.findings if f.highlightable)
    assert duplicate_finding.cell_range == "Sales!A2:Z2,A7:Z7"

    requests = build_highlight_requests(sales_structure, sales_health.findings)

    ranges = [r["repeatCell"]["range"] for r in requests]
    assert ranges == [
        {"sheetId": 0, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": 26},
        {"sheetId": 0, "startRowIndex": 6, "endRowIndex": 7, "startColumnIndex": 0, "endColumnIndex": 26},
    ]

    for request in requests:
        assert request["repeatCell"]["fields"] == "userEnteredFormat.backgroundColor"
        assert request["repeatCell"]["cell"]["userEnteredFormat"]["backgroundColor"] == HIGHLIGHT_COLOR


def test_build_highlight_requests_only_uses_the_existing_critical_tint(sales_structure, sales_health):
    # #FDE9E7 — the same tint used for CRITICAL tier pills/backgrounds
    # elsewhere in the report (extension/src/lib/theme.ts TIER_TINT.critical).
    assert HIGHLIGHT_COLOR == pytest.approx({"red": 0xFD / 255, "green": 0xE9 / 255, "blue": 0xE7 / 255})
    requests = build_highlight_requests(sales_structure, sales_health.findings)
    assert requests, "expected at least one highlight request from the fixture's duplicate rows"


def test_non_highlightable_finding_never_produces_a_highlight_request(sales_structure):
    non_highlightable = Finding(
        category=Category.MAINTAINABILITY,
        severity=Severity.LOW,
        description="Column A has an unclear header.",
        cell_range="Sales!A1",
        recommendation="Rename it.",
        highlightable=False,
    )
    assert build_highlight_requests(sales_structure, [non_highlightable]) == []


def test_highlightable_finding_with_unresolvable_sheet_name_is_skipped(sales_structure):
    # A cell_range naming a sheet that isn't in the structure (e.g. one
    # since renamed or removed) must be dropped, not raise.
    orphaned = Finding(
        category=Category.DATA_QUALITY,
        severity=Severity.HIGH,
        description="Duplicate rows.",
        cell_range="DoesNotExist!A2:Z2",
        recommendation="Remove them.",
        highlightable=True,
    )
    assert build_highlight_requests(sales_structure, [orphaned]) == []


def test_build_clear_requests_resets_to_no_fill():
    ranges = [{"sheetId": 0, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": 26}]
    requests = build_clear_requests(ranges)

    assert len(requests) == 1
    cell_format = requests[0]["repeatCell"]["cell"]["userEnteredFormat"]
    assert cell_format["backgroundColor"] == CLEAR_COLOR == {"red": 1.0, "green": 1.0, "blue": 1.0}
    assert requests[0]["repeatCell"]["range"] == ranges[0]
    assert requests[0]["repeatCell"]["fields"] == "userEnteredFormat.backgroundColor"


def test_count_affected_cells():
    ranges = [
        {"startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": 26},  # 1 row x 26 cols
        {"startRowIndex": 6, "endRowIndex": 7, "startColumnIndex": 0, "endColumnIndex": 26},  # 1 row x 26 cols
    ]
    assert count_affected_cells(ranges) == 52
    assert count_affected_cells([]) == 0


# ---------------------------------------------------------------------------
# Endpoint integration (dependency-overridden test DB, Sheets API mocked)
# ---------------------------------------------------------------------------


def _make_session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def client_with_test_db(monkeypatch, sales_raw):
    monkeypatch.setattr(main_module, "fetch_spreadsheet_raw_cached", lambda token, sid: sales_raw)
    monkeypatch.setattr(main_module, "get_user_email_sync", lambda token: "alice@example.com")

    batch_calls: list[list[dict]] = []

    def fake_apply_batch_update(access_token, spreadsheet_id, requests):
        batch_calls.append(requests)
        return {}

    monkeypatch.setattr(main_module, "apply_batch_update", fake_apply_batch_update)

    from fastapi.testclient import TestClient

    session_factory = _make_session_factory()

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    main_module.app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(main_module.app), session_factory, batch_calls
    finally:
        main_module.app.dependency_overrides.clear()


def test_highlight_duplicates_endpoint_applies_and_records(client_with_test_db):
    client, session_factory, batch_calls = client_with_test_db

    response = client.post("/sheets/mock-id/highlight-duplicates", json={"access_token": "tok"})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["ranges_highlighted"] == 2
    assert body["cells_affected"] == 52

    # Nothing was previously recorded, so this should be a single apply
    # call — no clear call yet.
    assert len(batch_calls) == 1
    assert all(req["repeatCell"]["cell"]["userEnteredFormat"]["backgroundColor"] == HIGHLIGHT_COLOR for req in batch_calls[0])

    session = session_factory()
    try:
        record = session.query(AppliedHighlight).one()
        assert record.spreadsheet_id == "mock-id"
        assert len(record.ranges) == 2
    finally:
        session.close()


def test_highlight_duplicates_clears_previous_ranges_before_reapplying(client_with_test_db):
    client, session_factory, batch_calls = client_with_test_db

    # First call establishes a recorded set of ranges.
    first = client.post("/sheets/mock-id/highlight-duplicates", json={"access_token": "tok"})
    assert first.status_code == 200
    assert len(batch_calls) == 1

    # A second call (e.g. re-analyzing after further edits) must clear the
    # previously-recorded ranges *before* applying the current findings'
    # ranges — never leaving stale highlighting behind.
    second = client.post("/sheets/mock-id/highlight-duplicates", json={"access_token": "tok"})
    assert second.status_code == 200
    assert len(batch_calls) == 3  # first call's apply, then this call's clear + apply

    clear_call, apply_call = batch_calls[1], batch_calls[2]
    assert all(req["repeatCell"]["cell"]["userEnteredFormat"]["backgroundColor"] == CLEAR_COLOR for req in clear_call)
    assert all(req["repeatCell"]["cell"]["userEnteredFormat"]["backgroundColor"] == HIGHLIGHT_COLOR for req in apply_call)

    # Still exactly one record afterward (upserted, not duplicated).
    session = session_factory()
    try:
        assert session.query(AppliedHighlight).count() == 1
    finally:
        session.close()


def test_highlight_duplicates_skips_write_when_email_unresolvable(client_with_test_db, monkeypatch):
    client, _session_factory, batch_calls = client_with_test_db
    monkeypatch.setattr(main_module, "get_user_email_sync", lambda token: None)

    response = client.post("/sheets/mock-id/highlight-duplicates", json={"access_token": "tok"})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["error"]
    assert batch_calls == []  # never wrote to the sheet without a way to track it


def test_clear_highlights_endpoint_clears_and_deletes_record(client_with_test_db):
    client, session_factory, batch_calls = client_with_test_db

    session = session_factory()
    try:
        user = get_or_create_user(session, "alice@example.com")
        fake_ranges = [{"sheetId": 0, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": 26}]
        upsert_applied_highlight(session, user, "mock-id", fake_ranges)
    finally:
        session.close()

    response = client.post("/sheets/mock-id/clear-highlights", json={"access_token": "tok"})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["ranges_highlighted"] == 0

    assert len(batch_calls) == 1
    assert all(req["repeatCell"]["cell"]["userEnteredFormat"]["backgroundColor"] == CLEAR_COLOR for req in batch_calls[0])

    session = session_factory()
    try:
        assert session.query(AppliedHighlight).count() == 0
    finally:
        session.close()


def test_clear_highlights_endpoint_is_a_no_op_when_nothing_recorded(client_with_test_db):
    client, _session_factory, batch_calls = client_with_test_db

    response = client.post("/sheets/mock-id/clear-highlights", json={"access_token": "tok"})
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert batch_calls == []
