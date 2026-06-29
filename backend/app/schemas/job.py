"""Job request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class JobCreate(BaseModel):
    source: str = Field(min_length=1, max_length=100)
    external_id: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    company: str = Field(min_length=1, max_length=255)
    location: str | None = None
    description: str | None = None
    apply_url: HttpUrl | None = None
    source_url: HttpUrl | None = None
    remote: bool = False
    employment_type: str | None = None
    posted_at: datetime | None = None


class JobRead(BaseModel):
    id: int
    source: str
    external_id: str
    title: str
    company: str
    location: str | None
    description: str | None
    apply_url: str | None
    source_url: str | None
    remote: bool
    employment_type: str | None
    posted_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobSearchResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[JobRead]
