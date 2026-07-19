"""Versioned, job-specific resume artifacts."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class TailoredResume(Base):
    __tablename__ = "tailored_resumes"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", "version", name="uq_tailored_resumes_user_job_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True, nullable=False)
    source_resume_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_resumes.id", ondelete="SET NULL"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    tailored_resume_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    headline: Mapped[str] = mapped_column(String(255), nullable=False)
    professional_summary: Mapped[str] = mapped_column(Text, nullable=False)
    core_skills: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    keywords_incorporated: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    unsupported_job_requirements: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    change_summary: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    truthfulness_warnings: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    estimated_alignment_score: Mapped[float] = mapped_column(Float, nullable=False)
    llm_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    llm_model: Mapped[str] = mapped_column(String(255), nullable=False)
    requested_render_mode: Mapped[str] = mapped_column(String(32), default="auto", nullable=False)
    actual_render_mode: Mapped[str] = mapped_column(String(32), default="ats", nullable=False)
    template_fidelity: Mapped[str] = mapped_column(String(32), default="standardized", nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_provider: Mapped[str] = mapped_column(String(50), default="database", nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
