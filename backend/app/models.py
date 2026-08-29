"""SQLAlchemy ORM models for the persistence layer.

Two tables cover what's asked for now — users, and a record of each health
report generated (which doubles as "scores over time": querying a
spreadsheet's reports ordered by created_at *is* its score history).
Nothing here exposes a "view my report history" endpoint yet (that's the
Pro feature); this is the schema + storage it will read from later.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    reports: Mapped[list["Report"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, email={self.email!r})"


class Report(Base):
    """One health-score computation for one spreadsheet at one point in
    time. category_scores mirrors analysis.health_score.CategoryScores as
    a plain JSON blob rather than its own columns, since it's a fixed
    write-once snapshot, not something queried by individual category."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    spreadsheet_id: Mapped[str] = mapped_column(String(128), index=True)
    spreadsheet_title: Mapped[str] = mapped_column(String(512), default="")
    overall_score: Mapped[float] = mapped_column(Float)
    category_scores: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    user: Mapped["User"] = relationship(back_populates="reports")

    def __repr__(self) -> str:
        return (
            f"Report(id={self.id!r}, spreadsheet_id={self.spreadsheet_id!r}, "
            f"overall_score={self.overall_score!r})"
        )
