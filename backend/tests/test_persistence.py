import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main_module
from analysis.health_score import CategoryScores, CategoryWeights, HealthReport
from app.db import get_db
from app.models import Base, Report, User
from app.repository import get_or_create_user, save_report

SALES_FIXTURE = Path(__file__).parent / "fixtures" / "sales_sheet_raw.json"


def _make_session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def db_session():
    session = _make_session_factory()()
    try:
        yield session
    finally:
        session.close()


def _sample_health_report(overall_score: float = 80.0) -> HealthReport:
    return HealthReport(
        overall_score=overall_score,
        category_scores=CategoryScores(
            data_quality=90, formula_quality=80, structure=70, maintainability=60, security=100
        ),
        weights=CategoryWeights(),
        findings=[],
    )


# --- Repository -----------------------------------------------------------


def test_get_or_create_user_creates_then_reuses(db_session):
    first = get_or_create_user(db_session, "alice@example.com")
    second = get_or_create_user(db_session, "alice@example.com")
    assert first.id == second.id
    assert db_session.query(User).count() == 1


def test_get_or_create_user_distinct_emails_are_distinct_users(db_session):
    alice = get_or_create_user(db_session, "alice@example.com")
    bob = get_or_create_user(db_session, "bob@example.com")
    assert alice.id != bob.id


def test_save_report_persists_scores(db_session):
    user = get_or_create_user(db_session, "alice@example.com")
    report = save_report(db_session, user, "sheet-123", "My Sheet", _sample_health_report())

    assert report.id is not None
    assert report.user_id == user.id
    assert report.spreadsheet_id == "sheet-123"
    assert report.spreadsheet_title == "My Sheet"
    assert report.overall_score == 80.0
    assert report.category_scores["security"] == 100


def test_reports_over_time_can_be_queried_in_order(db_session):
    user = get_or_create_user(db_session, "alice@example.com")
    for score in (50.0, 60.0, 70.0):
        save_report(db_session, user, "sheet-123", "My Sheet", _sample_health_report(score))

    reports = (
        db_session.query(Report).filter(Report.spreadsheet_id == "sheet-123").order_by(Report.id).all()
    )
    assert [r.overall_score for r in reports] == [50.0, 60.0, 70.0]


def test_deleting_a_user_cascades_to_their_reports(db_session):
    user = get_or_create_user(db_session, "alice@example.com")
    save_report(db_session, user, "sheet-123", "My Sheet", _sample_health_report())

    db_session.delete(user)
    db_session.commit()

    assert db_session.query(Report).count() == 0


# --- Endpoint integration (dependency-overridden test DB) ------------------


@pytest.fixture
def client_with_test_db(monkeypatch):
    sales_raw = json.loads(SALES_FIXTURE.read_text())
    monkeypatch.setattr(main_module, "fetch_spreadsheet_raw_cached", lambda token, sid: sales_raw)

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
        yield TestClient(main_module.app), session_factory
    finally:
        main_module.app.dependency_overrides.clear()


def test_health_endpoint_persists_a_report_when_email_is_resolvable(client_with_test_db, monkeypatch):
    client, session_factory = client_with_test_db
    monkeypatch.setattr(main_module, "get_user_email_sync", lambda token: "alice@example.com")

    response = client.post("/sheets/mock-id/health", json={"access_token": "tok"})
    assert response.status_code == 200

    session = session_factory()
    try:
        assert session.query(User).count() == 1
        report = session.query(Report).one()
        assert report.spreadsheet_id == "mock-id"
        assert report.overall_score == response.json()["overall_score"]
    finally:
        session.close()


def test_health_endpoint_succeeds_without_the_email_scope(client_with_test_db, monkeypatch):
    """A user who hasn't granted userinfo.email still gets their health
    report — persistence is a bonus, not a requirement."""
    client, session_factory = client_with_test_db
    monkeypatch.setattr(main_module, "get_user_email_sync", lambda token: None)

    response = client.post("/sheets/mock-id/health", json={"access_token": "tok"})
    assert response.status_code == 200

    session = session_factory()
    try:
        assert session.query(Report).count() == 0
    finally:
        session.close()


def test_health_endpoint_survives_a_persistence_failure(client_with_test_db, monkeypatch):
    """Simulates the DB being unreachable — the health report the user
    asked for must still come back successfully."""
    client, _session_factory = client_with_test_db

    def boom(token):
        raise RuntimeError("simulated database outage")

    monkeypatch.setattr(main_module, "get_user_email_sync", boom)

    response = client.post("/sheets/mock-id/health", json={"access_token": "tok"})
    assert response.status_code == 200
    assert "overall_score" in response.json()
