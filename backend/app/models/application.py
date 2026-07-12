"""User application-assistance records."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class ApplicationProfile(Base):
    __tablename__ = "application_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_application_profiles_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    github_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    work_authorization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requires_sponsorship: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    default_answers: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class JobApplication(Base):
    __tablename__ = "job_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True, nullable=False)
    mode: Mapped[str] = mapped_column(String(32), default="assisted", nullable=False)
    apply_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_values: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    missing_fields: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    user_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
