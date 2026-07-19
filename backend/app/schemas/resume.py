"""Resume request and response schemas."""

from datetime import datetime
from typing import Literal

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
    original_file_available: bool
    original_file_size: int | None
    original_file_sha256: str | None
    template_capability: Literal["original_docx", "ats_reconstruction"]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserResumeStatus(BaseModel):
    has_resume: bool
    resume: UserResumeRead | None = None


class TailoredResumeRequest(BaseModel):
    job_id: int = Field(gt=0)
    resume_text: str | None = Field(
        default=None,
        min_length=20,
        description="Optional source resume from the frontend. The saved resume is used when omitted.",
    )
    llm_key_id: int | None = Field(
        default=None,
        gt=0,
        description="Optional user-owned LLM key. The most recently updated active key is used when omitted.",
    )
    additional_instructions: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional truthful preferences such as desired emphasis or tone.",
    )
    render_mode: Literal["auto", "original", "ats"] = Field(
        default="auto",
        description=(
            "auto preserves a saved DOCX template when available; original requires a saved DOCX; "
            "ats always uses the clean JobPilot template."
        ),
    )


class TailoredResumeResponse(BaseModel):
    job_id: int
    job_title: str
    company: str
    source_resume_id: int | None
    tailored_resume_markdown: str
    headline: str
    professional_summary: str
    core_skills: list[str] = Field(default_factory=list)
    keywords_incorporated: list[str] = Field(default_factory=list)
    unsupported_job_requirements: list[str] = Field(default_factory=list)
    change_summary: list[str] = Field(default_factory=list)
    truthfulness_warnings: list[str] = Field(default_factory=list)
    estimated_alignment_score: float
    provider: str
    model: str


class TailoredResumeRead(TailoredResumeResponse):
    id: int
    user_id: int
    version: int
    filename: str
    content_type: str
    file_size: int
    storage_provider: str
    requested_render_mode: Literal["auto", "original", "ats"]
    actual_render_mode: Literal["original_docx", "ats"]
    template_fidelity: Literal["best_effort", "standardized"]
    pdf_render_mode: Literal["ats"]
    download_url: str
    pdf_download_url: str
    created_at: datetime
    updated_at: datetime
