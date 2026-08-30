"""SQLAlchemy ORM models for the persistence layer.

Users, a record of each health report generated (which doubles as "scores
over time": querying a spreadsheet's reports ordered by created_at *is* its
score history — nothing here exposes a "view my report history" endpoint
yet, that's the Pro feature; this is the schema + storage it will read from
later), and applied_highlights — the "Highlight duplicates in Sheet"
feature's record of what it last wrote to a spreadsheet, so a later call
knows exactly what to clear.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint, func
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


class AppliedHighlight(Base):
    """The most recent set of duplicate-row highlight ranges this backend
    wrote into a spreadsheet for a user. One row per (user, spreadsheet) —
    a new highlight-duplicates call overwrites it, a clear-highlights call
    (or a highlight-duplicates call that finds nothing to highlight)
    deletes it. `ranges` stores the Sheets API GridRange dicts that were
    written (see analysis.highlight.build_highlight_requests), so clearing
    them later never depends on re-deriving anything from the sheet's
    current (possibly since-changed) contents.
    """

    __tablename__ = "applied_highlights"
    __table_args__ = (UniqueConstraint("user_id", "spreadsheet_id", name="uq_applied_highlights_user_spreadsheet"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    spreadsheet_id: Mapped[str] = mapped_column(String(128), index=True)
    ranges: Mapped[list] = mapped_column(JSON)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return (
            f"AppliedHighlight(id={self.id!r}, spreadsheet_id={self.spreadsheet_id!r}, "
            f"ranges={len(self.ranges)!r})"
        )
