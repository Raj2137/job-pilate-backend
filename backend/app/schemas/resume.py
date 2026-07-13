"""Resume request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserResumeUpsert(BaseModel):
    resume_text: str = Field(min_length=20, description="Extracted plain text from the user's resume.")
    filename: str | None = Field(default=None, max_length=255)
    content_type: str | None = Field(default=None, max_length=100)


class UserResumeRead(BaseModel):
    id: int
    resume_text: str
    filename: str | None
    content_type: str | None
    character_count: int
    text_preview: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserResumeStatus(BaseModel):
    has_resume: bool
    resume: UserResumeRead | None = None
