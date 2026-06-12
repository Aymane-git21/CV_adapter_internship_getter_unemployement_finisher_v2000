"""SQLAlchemy models. New-generation schema — table names deliberately avoid
colliding with the legacy Flask tables (user/application/feedback) so both can
coexist in the same database during migration."""
from datetime import UTC, date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(Text, default=None)
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True, default=None)
    plan: Mapped[str] = mapped_column(String(16), default="free")  # free | plus | pro
    language: Mapped[str] = mapped_column(String(8), default="en")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), default=None)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64), default=None)
    gens_today: Mapped[int] = mapped_column(Integer, default=0)
    gens_date: Mapped[date | None] = mapped_column(Date, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    master_cvs: Mapped[list["MasterCV"]] = relationship(back_populates="user", lazy="noload")


class MasterCV(Base):
    __tablename__ = "master_cvs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), default="My CV")
    data: Mapped[dict | None] = mapped_column(JSON, default=None)  # CVData
    raw_text: Mapped[str | None] = mapped_column(Text, default=None)
    is_default: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="master_cvs", lazy="noload")


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, default=None)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    mime: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Job(Base):
    """One generation run for one job description."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, default=None)
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued|running|completed|failed
    language: Mapped[str] = mapped_column(String(8), default="en")
    job_description: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(String(200), default=None)
    company: Mapped[str | None] = mapped_column(String(200), default=None)
    analysis: Mapped[dict | None] = mapped_column(JSON, default=None)
    events: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    byok: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class Document(Base):
    """A generated, editable artifact: CV, cover letter, or outreach message."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"), index=True, default=None)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, default=None)
    kind: Mapped[str] = mapped_column(String(16))  # cv | letter | message
    title: Mapped[str] = mapped_column(String(255), default="Document")
    template_id: Mapped[str] = mapped_column(String(32), default="onyx")
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    data: Mapped[dict | None] = mapped_column(JSON, default=None)  # CVData / LetterData
    source: Mapped[str | None] = mapped_column(Text, default=None)  # Typst source
    mode: Mapped[str] = mapped_column(String(8), default="data")  # data | source
    text_content: Mapped[str | None] = mapped_column(Text, default=None)  # message kind
    photo_id: Mapped[str | None] = mapped_column(String(32), default=None)
    pdf: Mapped[bytes | None] = mapped_column(LargeBinary, default=None)  # cache
    score_before: Mapped[int | None] = mapped_column(Integer, default=None)
    score_after: Mapped[int | None] = mapped_column(Integer, default=None)
    keywords: Mapped[dict | None] = mapped_column(JSON, default=None)  # {matched, missing}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class FeedbackEntry(Base):
    __tablename__ = "feedback_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String(120), default=None)
    email: Mapped[str | None] = mapped_column(String(255), default=None)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GuestUsage(Base):
    """Daily generation counter for anonymous visitors, keyed by a salted IP hash."""

    __tablename__ = "guest_usage"
    __table_args__ = (UniqueConstraint("key_hash", "day", name="uq_guest_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(64), index=True)
    day: Mapped[date] = mapped_column(Date)
    count: Mapped[int] = mapped_column(Integer, default=0)
