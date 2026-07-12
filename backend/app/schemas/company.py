"""Company API schemas."""

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class CompanyRead(BaseModel):
    id: int
    name: str
    slug: str
    domain: str | None
    industry: str | None
    careers_url: str | None
    ats_type: str
    ats_identifier: str | None
    ats_confidence: str | None
    application_mode: str
    collection_status: str
    consecutive_failures: int
    circuit_open_until: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    is_active: bool
    last_checked_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanySearchResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[CompanyRead]


class CompanyResolveRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    website_url: HttpUrl | None = None
    careers_url: HttpUrl
    industry: str | None = Field(default=None, max_length=100)
