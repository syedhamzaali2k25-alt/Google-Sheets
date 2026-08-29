"""Small persistence helpers over app/models.py.

Kept deliberately thin — callers (main.py) own transaction boundaries and
error handling, since persistence here is a best-effort side effect of
computing a health report, not something that should ever fail the
request that triggered it.
"""

from sqlalchemy.orm import Session

from analysis.health_score import HealthReport
from app.models import Report, User


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
