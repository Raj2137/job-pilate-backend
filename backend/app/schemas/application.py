"""Application-assistance API schemas."""

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class ApplicationProfileUpdate(BaseModel):
    phone: str | None = Field(default=None, max_length=50)
    current_location: str | None = Field(default=None, max_length=255)
    linkedin_url: HttpUrl | None = None
    portfolio_url: HttpUrl | None = None
    github_url: HttpUrl | None = None
    resume_url: HttpUrl | None = None
    years_experience: int | None = Field(default=None, ge=0, le=80)
    work_authorization: str | None = Field(default=None, max_length=255)
    requires_sponsorship: bool | None = None
    default_answers: dict[str, str | bool | int | float | None] = Field(default_factory=dict)


class ApplicationProfileRead(ApplicationProfileUpdate):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApplicationPrepareRequest(BaseModel):
    job_id: int
    overrides: dict[str, str | bool | int | float | None] = Field(default_factory=dict)


class ApplicationStatusUpdate(BaseModel):
    status: str = Field(pattern="^(ready_for_review|opened|submitted|failed)$")
    user_confirmed: bool = False
    error: str | None = Field(default=None, max_length=2000)


class JobApplicationRead(BaseModel):
    id: int
    user_id: int
    job_id: int
    status: str
    mode: str
    apply_url: str | None
    field_values: dict
    missing_fields: list[str]
    user_confirmed: bool
    error: str | None
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
