"""Top-level integration test.

Drives the full user-facing flow — analyze a spreadsheet, then health,
documentation, changes, and export — through the real FastAPI app
(TestClient), the same way the extension's dashboard actually calls it.
Only the Google API calls are mocked (via the mock Sales/Notes and Drive
Activity fixtures used throughout the rest of the suite); everything else
— routing, caching, analysis, PDF generation — runs for real.
"""

import json
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

import analysis.change_history as change_history
import app.google_sheets as google_sheets
import app.main as main_module
from app.google_sheets import SheetsAccessError

SALES_FIXTURE = Path(__file__).parent / "fixtures" / "sales_sheet_raw.json"
ACTIVITY_FIXTURE = Path(__file__).parent / "fixtures" / "drive_activity_sample.json"
SPREADSHEET_ID = "mock-spreadsheet-id"
ACCESS_TOKEN = "test-access-token"


@pytest.fixture
def fetch_calls():
    return {"raw": 0, "activity": 0}


@pytest.fixture
def client(monkeypatch, fetch_calls):
    sales_raw = json.loads(SALES_FIXTURE.read_text())
    activity_raw = json.loads(ACTIVITY_FIXTURE.read_text())

    def fake_fetch_raw(access_token, spreadsheet_id):
        assert access_token == ACCESS_TOKEN
        assert spreadsheet_id == SPREADSHEET_ID
        fetch_calls["raw"] += 1
        return sales_raw

    def fake_fetch_activity(access_token, spreadsheet_id, since, until=None):
        assert access_token == ACCESS_TOKEN
        fetch_calls["activity"] += 1
        return activity_raw

    # A stable revision means every step in the flow shares one cached raw
    # fetch instead of re-hitting the (mocked) Sheets API each time.
    monkeypatch.setattr(google_sheets, "fetch_spreadsheet_raw", fake_fetch_raw)
    monkeypatch.setattr(google_sheets, "fetch_spreadsheet_revision", lambda token, sid: "revision-1")
    monkeypatch.setattr(change_history, "fetch_change_activity", fake_fetch_activity)
    # Skip the persistence side effect here — it has its own dedicated
    # tests in test_persistence.py; this test is about the analysis flow.
    monkeypatch.setattr(main_module, "get_user_email_sync", lambda token: None)

    google_sheets._raw_cache.clear()
    change_history._activity_cache.clear()

    return TestClient(main_module.app)


def test_full_analyze_flow_end_to_end(client, fetch_calls):
    # Step 1: raw fetch — what the extension calls first to detect the sheet.
    raw_response = client.post(f"/sheets/{SPREADSHEET_ID}/raw", json={"access_token": ACCESS_TOKEN})
    assert raw_response.status_code == 200
    raw_body = raw_response.json()
    assert raw_body["title"] == "Q1 Sales Tracker"
    assert {sheet["title"] for sheet in raw_body["sheets"]} == {"Sales", "Notes"}

    # Step 2: health score.
    health_response = client.post(f"/sheets/{SPREADSHEET_ID}/health", json={"access_token": ACCESS_TOKEN})
    assert health_response.status_code == 200
    health_body = health_response.json()
    assert health_body["overall_score"] == pytest.approx(64.2, abs=0.01)
    assert len(health_body["findings"]) == 13
    assert any(finding["severity"] == "high" for finding in health_body["findings"])

    # Step 3: documentation.
    doc_response = client.post(f"/sheets/{SPREADSHEET_ID}/documentation", json={"access_token": ACCESS_TOKEN})
    assert doc_response.status_code == 200
    doc_body = doc_response.json()
    assert doc_body["title"] == "Q1 Sales Tracker"
    assert doc_body["source"] == "rule_based"
    sales_summary = next(s["summary"] for s in doc_body["sheet_summaries"] if s["sheet_name"] == "Sales")
    assert "Total is calculated from Units" in sales_summary

    # Step 4: change history.
    changes_response = client.get(
        f"/sheets/{SPREADSHEET_ID}/changes?days=30",
        headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
    )
    assert changes_response.status_code == 200
    changes_body = changes_response.json()
    assert changes_body["total_edits"] == 6
    assert changes_body["data_granularity"] == "file_level"
    assert len(changes_body["contributors"]) == 2

    # Step 5: export — combines every report above into one PDF.
    export_response = client.post(
        f"/sheets/{SPREADSHEET_ID}/export", json={"access_token": ACCESS_TOKEN, "days": 30}
    )
    assert export_response.status_code == 200
    assert export_response.headers["content-type"] == "application/pdf"
    assert export_response.content[:5] == b"%PDF-"

    reader = PdfReader(BytesIO(export_response.content))
    pdf_text = " ".join(page.extract_text() for page in reader.pages)
    assert "Q1 Sales Tracker" in pdf_text
    assert "Change Activity" in pdf_text
    assert "people/200" in pdf_text
    # The score shown in the PDF cover page matches what /health reported.
    assert str(round(health_body["overall_score"])) in pdf_text

    # /raw, /health, /documentation, and /export all hit the same
    # unchanged spreadsheet with the same token — the raw-fetch cache
    # (task: "doesn't re-hit the Google API unnecessarily") should have
    # made exactly one real fetch for the whole flow, not four.
    assert fetch_calls["raw"] == 1
    # Change history was queried by both /changes and /export.
    assert fetch_calls["activity"] >= 1


def test_flow_stops_cleanly_on_an_invalid_token(monkeypatch, fetch_calls):
    def fake_fetch_raw(access_token, spreadsheet_id):
        raise SheetsAccessError(401, "Google access token is invalid or expired.")

    monkeypatch.setattr(google_sheets, "fetch_spreadsheet_raw", fake_fetch_raw)
    monkeypatch.setattr(google_sheets, "fetch_spreadsheet_revision", lambda token, sid: None)
    google_sheets._raw_cache.clear()

    client = TestClient(main_module.app)
    for path in ("raw", "structure", "health", "documentation"):
        response = client.post(f"/sheets/{SPREADSHEET_ID}/{path}", json={"access_token": "bad-token"})
        assert response.status_code == 401, f"/{path} should reject an invalid token"
