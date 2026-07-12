"""Persistent collection targets and their execution history."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class SearchSegment(Base):
    __tablename__ = "search_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    query: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), index=True, nullable=True)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    job_limit: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    initial_date_posted: Mapped[str] = mapped_column(String(32), default="past_week", nullable=False)
    incremental_date_posted: Mapped[str] = mapped_column(String(32), default="past_24h", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True, nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime, index=True, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CollectionRun(Base):
    __tablename__ = "collection_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    segment_id: Mapped[int] = mapped_column(ForeignKey("search_segments.id"), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enriched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
