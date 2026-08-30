"""Small persistence helpers over app/models.py.

Kept deliberately thin — callers (main.py) own transaction boundaries and
error handling, since persistence here is a best-effort side effect of
computing a health report, not something that should ever fail the
request that triggered it.
"""

from typing import Any

from sqlalchemy.orm import Session

from analysis.health_score import HealthReport
from app.models import AppliedHighlight, Report, User


def get_or_create_user(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email).one_or_none()
    if user is not None:
        return user

    user = User(email=email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def save_report(
    db: Session,
    user: User,
    spreadsheet_id: str,
    spreadsheet_title: str,
    health: HealthReport,
) -> Report:
    report = Report(
        user_id=user.id,
        spreadsheet_id=spreadsheet_id,
        spreadsheet_title=spreadsheet_title,
        overall_score=health.overall_score,
        category_scores=health.category_scores.model_dump(),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def get_applied_highlight(db: Session, user: User, spreadsheet_id: str) -> AppliedHighlight | None:
    return (
        db.query(AppliedHighlight)
        .filter(AppliedHighlight.user_id == user.id, AppliedHighlight.spreadsheet_id == spreadsheet_id)
        .one_or_none()
    )


def upsert_applied_highlight(
    db: Session, user: User, spreadsheet_id: str, ranges: list[dict[str, Any]]
) -> AppliedHighlight:
    """Records the ranges just written to the sheet, replacing whatever was
    previously recorded for this (user, spreadsheet) pair. Unlike
    save_report above, this one is a functional dependency of the highlight
    feature (not best-effort telemetry): a later clear-highlights or
    highlight-duplicates call reads this row to know what to clear, so
    callers must not swallow failures here silently."""
    existing = get_applied_highlight(db, user, spreadsheet_id)
    if existing is not None:
        existing.ranges = ranges
        db.commit()
        db.refresh(existing)
        return existing

    record = AppliedHighlight(user_id=user.id, spreadsheet_id=spreadsheet_id, ranges=ranges)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def delete_applied_highlight(db: Session, user: User, spreadsheet_id: str) -> None:
    existing = get_applied_highlight(db, user, spreadsheet_id)
    if existing is not None:
        db.delete(existing)
        db.commit()
