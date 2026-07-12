"""High-level launch catalogue collection orchestration."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.search_segment import SearchSegment
from app.providers.catalog import COMPANY_SLUGS_BY_ENUM
from app.providers.sources import JobSource
from app.repositories.search_segment_repository import (
    ensure_company_segments,
    ensure_linkedin_segment,
    make_segment_due,
    utc_now,
)
from app.scheduler.job_scheduler import run_scheduler_cycle
from app.schemas.job import CatalogCollectionRequest, CatalogCollectionResponse
from app.schemas.search_segment import SearchSegmentCreate
from app.services.company_service import seed_default_companies


def trigger_catalog_collection(db: Session, payload: CatalogCollectionRequest) -> CatalogCollectionResponse:
    seed_default_companies(db)

    company_ids = _selected_company_ids(db, payload) if payload.include_companies else None
    ats_types = {platform.value for platform in payload.ats_platforms} if payload.ats_platforms else None

    company_segments_created = 0
    if payload.include_companies:
        company_segments_created = ensure_company_segments(
            db,
            interval_minutes=payload.interval_minutes,
            company_ids=company_ids,
            ats_types=ats_types,
            job_limit=payload.company_job_limit,
        )
        _mark_company_segments_due(db, company_ids=company_ids, ats_types=ats_types)

    linkedin_segments = 0
    if payload.include_linkedin:
        for search in payload.linkedin_searches:
            ensure_linkedin_segment(
                db,
                SearchSegmentCreate(
                    source=JobSource.LINKEDIN,
                    query=search.query,
                    location=search.location,
                    interval_minutes=payload.interval_minutes,
                    job_limit=payload.linkedin_job_limit,
                    initial_date_posted=payload.initial_date_posted,
                    incremental_date_posted=payload.incremental_date_posted,
                    priority=100,
                ),
            )
            linkedin_segments += 1

    total_segments = db.query(SearchSegment).filter(SearchSegment.is_active.is_(True)).count()
    due_segments = _count_due_segments(db)

    scheduler_claimed = 0
    scheduler_completed = 0
    scheduler_failed = 0
    if payload.run_now:
        result = run_scheduler_cycle(
            db,
            worker_id="api-catalog-trigger",
            batch_size=payload.run_batch_size,
            lease_minutes=15,
        )
        scheduler_claimed = result.claimed
        scheduler_completed = result.completed
        scheduler_failed = result.failed
        due_segments = _count_due_segments(db)

    mode = "started" if payload.run_now else "scheduled"
    return CatalogCollectionResponse(
        status=mode,
        company_segments_created=company_segments_created,
        linkedin_segments_created_or_updated=linkedin_segments,
        total_segments=total_segments,
        due_segments=due_segments,
        scheduler_claimed=scheduler_claimed,
        scheduler_completed=scheduler_completed,
        scheduler_failed=scheduler_failed,
        message=(
            "Catalogue collection plan is ready. The worker will process due segments one by one."
            if not payload.run_now
            else "Catalogue collection plan is ready and an immediate controlled batch was processed."
        ),
    )


def _selected_company_ids(db: Session, payload: CatalogCollectionRequest) -> set[int] | None:
    if not payload.companies:
        return None
    slugs = [COMPANY_SLUGS_BY_ENUM[company] for company in payload.companies]
    rows = db.query(Company.id).filter(Company.slug.in_(slugs), Company.is_active.is_(True)).all()
    return {row.id for row in rows}


def _mark_company_segments_due(
    db: Session,
    *,
    company_ids: set[int] | None,
    ats_types: set[str] | None,
) -> None:
    query = db.query(SearchSegment).join(Company, SearchSegment.company_id == Company.id).filter(
        SearchSegment.company_id.is_not(None),
        SearchSegment.is_active.is_(True),
    )
    if company_ids is not None:
        query = query.filter(SearchSegment.company_id.in_(company_ids))
    if ats_types is not None:
        query = query.filter(Company.ats_type.in_(ats_types))
    for segment in query.all():
        make_segment_due(db, segment)


def _count_due_segments(db: Session) -> int:
    now = utc_now()
    return (
        db.query(func.count(SearchSegment.id))
        .filter(SearchSegment.is_active.is_(True), SearchSegment.next_run_at <= now)
        .scalar()
        or 0
    )
