"""Job search routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.providers.sources import DEFAULT_SELECTED_SOURCES, SOURCE_METADATA, JobSource
from app.repositories.job_repository import search_jobs, upsert_job
from app.repositories.job_repository import list_job_filter_options
from app.repositories.search_segment_repository import (
    ensure_linkedin_segment,
    get_segment,
    list_runs,
    list_segments,
    make_segment_due,
    pause_segment,
)
from app.schemas.job import (
    CatalogCollectionRequest,
    CatalogCollectionResponse,
    CompanyJobCollectionRequest,
    CompanyJobCollectionResult,
    CompleteJobRunRequest,
    FreshJobRunRequest,
    JobCollectionRequest,
    JobCollectionResult,
    JobCreate,
    JobDiscoveryRequest,
    JobDiscoveryResponse,
    JobFiltersResponse,
    JobRead,
    JobRunResponse,
    JobSearchResponse,
    JobSourceRead,
    LinkedInEnrichmentRequest,
    LinkedInEnrichmentResult,
    ResumeJobMatchRequest,
    ResumeJobMatchResponse,
)
from app.ai.job_matcher import match_jobs_for_resume
from app.services.catalog_collection_service import trigger_catalog_collection
from app.services.job_collection_service import collect_company_jobs, collect_jobs, enrich_stored_linkedin_jobs
from app.services.job_discovery_service import discover_jobs
from app.services.job_run_service import run_complete_job_collection, run_fresh_job_collection
from app.schemas.search_segment import (
    CollectionRunRead,
    SearchSegmentCreate,
    SearchSegmentList,
    SearchSegmentRead,
)

router = APIRouter()


@router.post("/segments", response_model=SearchSegmentRead, status_code=status.HTTP_201_CREATED)
def create_search_segment(
    payload: SearchSegmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SearchSegmentRead:
    return ensure_linkedin_segment(db, payload)


@router.get("/segments", response_model=SearchSegmentList)
def get_search_segments(
    active_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SearchSegmentList:
    total, segments = list_segments(db, active_only=active_only)
    return SearchSegmentList(total=total, items=segments)


@router.get("/segments/{segment_id}/runs", response_model=list[CollectionRunRead])
def get_search_segment_runs(
    segment_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CollectionRunRead]:
    if get_segment(db, segment_id) is None:
        raise HTTPException(status_code=404, detail="Search segment not found")
    return list_runs(db, segment_id=segment_id, limit=limit)


@router.post("/segments/{segment_id}/run", response_model=SearchSegmentRead)
def schedule_search_segment_now(
    segment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SearchSegmentRead:
    segment = get_segment(db, segment_id)
    if segment is None:
        raise HTTPException(status_code=404, detail="Search segment not found")
    return make_segment_due(db, segment)


@router.post("/segments/{segment_id}/pause", response_model=SearchSegmentRead)
def pause_search_segment(
    segment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SearchSegmentRead:
    segment = get_segment(db, segment_id)
    if segment is None:
        raise HTTPException(status_code=404, detail="Search segment not found")
    return pause_segment(db, segment)


@router.get("/sources", response_model=list[JobSourceRead])
def list_sources(current_user: User = Depends(get_current_user)) -> list[JobSourceRead]:
    return [
        JobSourceRead(
            key=source,
            label=metadata["label"],
            category=metadata["category"],
            status=metadata["status"],
            default_selected=source in DEFAULT_SELECTED_SOURCES,
            notes=metadata["notes"],
        )
        for source, metadata in SOURCE_METADATA.items()
    ]


@router.post("/collect", response_model=JobCollectionResult)
def collect(
    payload: JobCollectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobCollectionResult:
    return collect_jobs(db, payload)


@router.post("/catalog/collect", response_model=CatalogCollectionResponse)
def collect_catalog(
    payload: CatalogCollectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CatalogCollectionResponse:
    return trigger_catalog_collection(db, payload)


@router.post("/run/complete", response_model=JobRunResponse)
def run_complete_collection(
    payload: CompleteJobRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobRunResponse:
    return run_complete_job_collection(db, payload)


@router.post("/run/fresh", response_model=JobRunResponse)
def run_fresh_collection(
    payload: FreshJobRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobRunResponse:
    return run_fresh_job_collection(db, payload)


@router.post("/collect/company", response_model=CompanyJobCollectionResult)
def collect_company(
    payload: CompanyJobCollectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CompanyJobCollectionResult:
    return collect_company_jobs(db, payload)


@router.post("/enrich/linkedin", response_model=LinkedInEnrichmentResult)
def enrich_linkedin(
    payload: LinkedInEnrichmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LinkedInEnrichmentResult:
    return enrich_stored_linkedin_jobs(db, payload)


@router.post("/discover", response_model=JobDiscoveryResponse)
def discover(
    payload: JobDiscoveryRequest,
    current_user: User = Depends(get_current_user),
) -> JobDiscoveryResponse:
    return discover_jobs(payload)


@router.get("/filters", response_model=JobFiltersResponse)
def filters(
    top_limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobFiltersResponse:
    return JobFiltersResponse(**list_job_filter_options(db, top_limit=top_limit))


@router.post("/match", response_model=ResumeJobMatchResponse)
def match_jobs(
    payload: ResumeJobMatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResumeJobMatchResponse:
    return match_jobs_for_resume(db, payload, current_user)


@router.get("/search", response_model=JobSearchResponse)
def search(
    query: str | None = Query(default=None, description="Search title, company, and description"),
    location: str | None = Query(default=None),
    source: str | None = Query(default=None),
    remote: bool | None = Query(default=None),
    application_method: str | None = Query(default=None, description="easy_apply or external"),
    details_status: str | None = Query(default=None, description="pending, complete, or failed"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobSearchResponse:
    total, jobs = search_jobs(
        db,
        query=query,
        location=location,
        source=source,
        remote=remote,
        application_method=application_method,
        details_status=details_status,
        limit=limit,
        offset=offset,
    )
    return JobSearchResponse(total=total, limit=limit, offset=offset, items=jobs)


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_or_update_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobRead:
    return upsert_job(db, payload)
