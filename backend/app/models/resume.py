"""User-owned resume records."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class UserResume(Base):
    __tablename__ = "user_resumes"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_resumes_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    resume_text: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    original_file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    original_file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    original_storage_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    original_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    original_file_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
