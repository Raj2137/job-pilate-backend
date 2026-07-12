"""Company career source model."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    careers_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ats_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    ats_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ats_confidence: Mapped[str | None] = mapped_column(String(32), nullable=True)
    application_mode: Mapped[str] = mapped_column(String(32), default="assisted", nullable=False)
    collection_status: Mapped[str] = mapped_column(String(32), default="pending", index=True, nullable=False)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    circuit_open_until: Mapped[datetime | None] = mapped_column(DateTime, index=True, nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
