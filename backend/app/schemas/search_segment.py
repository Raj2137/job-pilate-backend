"""Collection segment API schemas."""

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.providers.sources import JobSource


class SearchSegmentCreate(BaseModel):
    source: JobSource = JobSource.LINKEDIN
    query: str | None = Field(default=None, min_length=2, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    interval_minutes: int = Field(default=60, ge=15, le=1440)
    job_limit: int = Field(default=50, ge=1, le=50)
    initial_date_posted: str = Field(default="past_week", max_length=32)
    incremental_date_posted: str = Field(default="past_24h", max_length=32)
    priority: int = Field(default=100, ge=1, le=1000)

    @model_validator(mode="after")
    def validate_source(self) -> "SearchSegmentCreate":
        if self.source != JobSource.LINKEDIN:
            raise ValueError("User-created search segments currently support LinkedIn discovery only")
        if not self.query:
            raise ValueError("Query is required for LinkedIn search segments")
        return self


class SearchSegmentRead(BaseModel):
    id: int
    key: str
    source: str
    query: str | None
    location: str | None
    company_id: int | None
    interval_minutes: int
    job_limit: int
    initial_date_posted: str
    incremental_date_posted: str
    priority: int
    is_active: bool
    status: str
    next_run_at: datetime
    last_started_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    run_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SearchSegmentList(BaseModel):
    total: int
    items: list[SearchSegmentRead]


class CollectionRunRead(BaseModel):
    id: int
    segment_id: int
    source: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    fetched: int
    created: int
    updated: int
    enriched: int
    failed: int
    error: str | None

    model_config = {"from_attributes": True}
