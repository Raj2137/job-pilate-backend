"""Job request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl

from app.providers.catalog import DEFAULT_FULL_COVERAGE_SEARCHES, DEFAULT_LINKEDIN_SEARCHES, LaunchCompany, MajorAtsPlatform
from app.providers.sources import DEFAULT_SELECTED_SOURCES, JobSource


class JobCreate(BaseModel):
    source: str = Field(min_length=1, max_length=100)
    external_id: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    company: str = Field(min_length=1, max_length=255)
    location: str | None = None
    description: str | None = None
    apply_url: HttpUrl | None = None
    source_url: HttpUrl | None = None
    company_url: HttpUrl | None = None
    remote: bool = False
    employment_type: str | None = None
    seniority_level: str | None = None
    application_method: str | None = None
    details_status: str | None = None
    details_attempts: int | None = None
    details_error: str | None = None
    details_fetched_at: datetime | None = None
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
    company_url: str | None
    remote: bool
    employment_type: str | None
    seniority_level: str | None
    application_method: str | None
    details_status: str | None
    details_attempts: int
    details_error: str | None
    details_fetched_at: datetime | None
    posted_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobSearchResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[JobRead]


class JobFilterOption(BaseModel):
    value: str
    count: int


class JobFiltersResponse(BaseModel):
    total_jobs: int
    jobs_with_jd: int
    jobs_without_jd: int
    sources: list[JobFilterOption]
    companies: list[JobFilterOption]
    locations: list[JobFilterOption]
    employment_types: list[JobFilterOption]
    application_methods: list[JobFilterOption]
    details_statuses: list[JobFilterOption]
    remote: list[JobFilterOption]


class JobSourceRead(BaseModel):
    key: JobSource
    label: str
    category: str
    status: str
    default_selected: bool
    notes: str


class JobCollectionRequest(BaseModel):
    sources: list[JobSource] = Field(default_factory=lambda: list(DEFAULT_SELECTED_SOURCES))
    query: str | None = Field(default=None, description="Job title or keywords for job board sources")
    location: str | None = Field(default=None, description="Location for job board sources")
    job_board_limit: int = Field(default=25, ge=1, le=1000)
    date_posted: str | None = Field(
        default="past_24h",
        description="Freshness filter for job-board connectors: any, past_24h, past_week, or past_month",
    )
    linkedin_enrich_details: bool = Field(
        default=True,
        description="Fetch descriptions and application methods for LinkedIn jobs that are not enriched yet",
    )
    linkedin_detail_limit: int = Field(default=25, ge=0, le=100)
    include_default_career_pages: bool = True
    greenhouse_boards: list[str] = Field(default_factory=list)
    lever_sites: list[str] = Field(default_factory=list)


class JobSourceCollectionResult(BaseModel):
    source: JobSource
    status: str
    fetched: int
    saved: int
    created: int = 0
    updated: int = 0
    enriched: int = 0
    enrichment_failed: int = 0
    message: str | None = None
    search_url: str | None = None


class JobCollectionResult(BaseModel):
    total_saved: int
    results: list[JobSourceCollectionResult]


class LinkedInEnrichmentRequest(BaseModel):
    limit: int = Field(default=25, ge=1, le=100)


class LinkedInEnrichmentResult(BaseModel):
    attempted: int
    enriched: int
    failed: int
    remaining: int


class CompanyJobCollectionRequest(BaseModel):
    company_name: str = Field(min_length=1)
    query: str | None = None
    location: str | None = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class CompanyJobCollectionResult(BaseModel):
    company: str
    careers_url: str | None
    ats_type: str
    ats_identifier: str | None
    status: str
    fetched: int
    saved: int
    created: int = 0
    updated: int = 0
    message: str | None = None
    jobs: list[JobRead] = Field(default_factory=list)


class JobDiscoveryRequest(BaseModel):
    sources: list[JobSource] = Field(default_factory=lambda: [JobSource.LINKEDIN, JobSource.INDEED, JobSource.CAREER_PAGES])
    query: str = Field(min_length=2, description="Job title or keywords")
    location: str | None = None
    limit_per_source: int = Field(default=10, ge=1, le=25)


class JobDiscoveryItem(BaseModel):
    title: str
    url: str


class JobDiscoverySourceResult(BaseModel):
    source: JobSource
    status: str
    found: int
    message: str | None = None
    items: list[JobDiscoveryItem]


class JobDiscoveryResponse(BaseModel):
    total_found: int
    results: list[JobDiscoverySourceResult]


class CatalogLinkedInSearch(BaseModel):
    query: str = Field(min_length=2, max_length=255)
    location: str | None = Field(default=None, max_length=255)


class CatalogCollectionRequest(BaseModel):
    include_companies: bool = True
    companies: list[LaunchCompany] | None = Field(
        default=None,
        description="If omitted, all launch companies are included.",
    )
    ats_platforms: list[MajorAtsPlatform] | None = Field(
        default=None,
        description="Optional company filter by detected/curated ATS platform.",
    )
    include_linkedin: bool = True
    linkedin_searches: list[CatalogLinkedInSearch] = Field(
        default_factory=lambda: [
            CatalogLinkedInSearch(query=query, location=location)
            for query, location in DEFAULT_LINKEDIN_SEARCHES
        ],
    )
    interval_minutes: int = Field(default=60, ge=30, le=1440)
    company_job_limit: int = Field(default=500, ge=1, le=500)
    linkedin_job_limit: int = Field(default=50, ge=1, le=50)
    initial_date_posted: str = Field(
        default="past_month",
        description="First-run LinkedIn freshness window. Use past_week or past_month for the 14-21 day backfill goal.",
    )
    incremental_date_posted: str = Field(default="past_24h")
    run_now: bool = Field(
        default=False,
        description="If true, immediately runs a limited scheduler batch after creating/updating segments.",
    )
    run_batch_size: int = Field(default=5, ge=1, le=50)


class CatalogCollectionResponse(BaseModel):
    status: str
    company_segments_created: int
    linkedin_segments_created_or_updated: int
    total_segments: int
    due_segments: int
    scheduler_claimed: int = 0
    scheduler_completed: int = 0
    scheduler_failed: int = 0
    message: str


class JobRunSearch(BaseModel):
    query: str = Field(min_length=2, max_length=255)
    location: str | None = Field(default=None, max_length=255)


class CompleteJobRunRequest(BaseModel):
    include_companies: bool = True
    companies: list[LaunchCompany] | None = Field(
        default=None,
        description="If omitted, all launch companies are included.",
    )
    ats_platforms: list[MajorAtsPlatform] | None = Field(
        default=None,
        description="Optional filter for companies by curated/detected ATS platform.",
    )
    include_job_boards: bool = True
    sources: list[JobSource] = Field(
        default_factory=lambda: [
            JobSource.LINKEDIN,
        ],
        description="Job boards run by query/location. Add planned sources explicitly as connectors are built.",
    )
    searches: list[JobRunSearch] = Field(
        default_factory=lambda: [
            JobRunSearch(query=query, location=location)
            for query, location in DEFAULT_FULL_COVERAGE_SEARCHES
        ],
    )
    company_job_limit: int = Field(default=500, ge=1, le=500)
    job_board_limit: int = Field(default=50, ge=1, le=100)
    date_posted: str | None = Field(
        default="past_month",
        description="Freshness window for job boards that support it.",
    )
    linkedin_enrich_details: bool = True
    linkedin_detail_limit: int = Field(default=25, ge=0, le=100)
    max_parallel_company_runs: int = Field(default=8, ge=1, le=25)
    max_parallel_search_runs: int = Field(default=1, ge=1, le=12)
    job_board_request_delay_seconds: float = Field(
        default=2.0,
        ge=0,
        le=60,
        description="Minimum delay between job-board search requests in this run.",
    )


class FreshJobRunRequest(CompleteJobRunRequest):
    date_posted: str | None = Field(
        default="past_24h",
        description="Freshness window for job boards that support it.",
    )
    company_job_limit: int = Field(default=500, ge=1, le=500)
    job_board_limit: int = Field(default=50, ge=1, le=100)


class JobRunResponse(BaseModel):
    status: str
    mode: str
    companies_attempted: int
    searches_attempted: int
    total_fetched: int
    total_saved: int
    total_created: int
    total_updated: int
    total_enriched: int
    total_failed: int
    total_skipped: int = 0
    total_unsupported: int = 0
    jobs_with_descriptions: int = 0
    jobs_missing_descriptions: int = 0
    jobs_with_jd: int = 0
    jobs_without_jd: int = 0
    jd_coverage_percent: float = 0.0
    coverage_notes: list[str] = Field(default_factory=list)
    error_summary: list[str] = Field(default_factory=list)
    company_results: list[CompanyJobCollectionResult] = Field(default_factory=list)
    source_results: list[JobSourceCollectionResult] = Field(default_factory=list)
    message: str


class ResumeJobMatchRequest(BaseModel):
    resume_text: str = Field(min_length=20, description="Plain text resume/profile content")
    job_title: str | None = Field(default=None, description="Primary target job title or keywords")
    target_roles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    years_experience: int | None = Field(default=None, ge=0, le=60)
    remote: bool | None = None
    source: str | None = None
    posted_within_days: int | None = Field(
        default=None,
        ge=1,
        le=365,
        description="Only consider jobs posted in the last N days when posted_at is available.",
    )
    latest_first: bool = True
    require_jd: bool = True
    candidate_limit: int = Field(default=500, ge=20, le=2000)
    limit: int = Field(default=25, ge=1, le=100)
    use_llm: bool = False
    llm_key_id: int | None = None
    llm_top_k: int = Field(default=10, ge=1, le=50)


class ResumeJobMatchItem(BaseModel):
    job: JobRead
    score: float
    matched_keywords: list[str]
    missing_keywords: list[str]
    experience_signal: str
    reasons: list[str]


class ResumeJobMatchResponse(BaseModel):
    total_candidates: int
    returned: int
    resume_keywords: list[str]
    relaxed: bool = False
    filter_trace: list[str] = Field(default_factory=list)
    llm_used: bool = False
    llm_status: str | None = None
    items: list[ResumeJobMatchItem]
