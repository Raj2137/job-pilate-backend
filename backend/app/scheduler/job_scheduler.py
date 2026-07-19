"""Durable hourly collection scheduler."""

from __future__ import annotations

import os
import socket
import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import SessionLocal, create_db_and_tables
from app.models.company import Company
from app.models.search_segment import SearchSegment
from app.providers.sources import JobSource
from app.repositories.search_segment_repository import (
    begin_run,
    claim_due_segments,
    complete_run,
    ensure_company_segments,
    fail_run,
)
from app.schemas.job import CompanyJobCollectionRequest, JobCollectionRequest, LinkedInEnrichmentRequest
from app.services.company_service import seed_default_companies
from app.services.job_collection_service import collect_company_jobs, collect_jobs, enrich_stored_linkedin_jobs


@dataclass
class SchedulerCycleResult:
    claimed: int = 0
    completed: int = 0
    failed: int = 0
    enriched_backlog: int = 0


def run_scheduler_cycle(
    db: Session,
    *,
    worker_id: str,
    batch_size: int,
    lease_minutes: int,
    enrichment_batch_size: int = 0,
) -> SchedulerCycleResult:
    result = SchedulerCycleResult()
    segments = claim_due_segments(
        db,
        worker_id=worker_id,
        limit=batch_size,
        lease_minutes=lease_minutes,
    )
    result.claimed = len(segments)

    for segment in segments:
        run = begin_run(db, segment)
        try:
            stats = _run_segment(db, segment)
            complete_run(db, segment=segment, run=run, **stats)
            result.completed += 1
        except Exception as exc:
            db.rollback()
            fail_run(db, segment=segment, run=run, error=str(exc))
            result.failed += 1

    if enrichment_batch_size > 0:
        enrichment = enrich_stored_linkedin_jobs(
            db,
            LinkedInEnrichmentRequest(limit=enrichment_batch_size),
        )
        result.enriched_backlog = enrichment.enriched

    return result


def run_scheduler_forever() -> None:
    settings = get_settings()
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    create_db_and_tables()
    seed_db = SessionLocal()
    try:
        seed_default_companies(seed_db)
    finally:
        seed_db.close()

    while True:
        db = SessionLocal()
        try:
            ensure_company_segments(db, interval_minutes=settings.job_collection_interval_minutes)
            run_scheduler_cycle(
                db,
                worker_id=worker_id,
                batch_size=settings.scheduler_batch_size,
                lease_minutes=settings.scheduler_lease_minutes,
                enrichment_batch_size=settings.linkedin_enrichment_batch_size,
            )
        finally:
            db.close()
        time.sleep(settings.scheduler_poll_seconds)


def _run_segment(db: Session, segment: SearchSegment) -> dict[str, int]:
    if segment.company_id is not None:
        company = db.get(Company, segment.company_id)
        if company is None:
            raise RuntimeError("Scheduled company no longer exists")
        collection = collect_company_jobs(
            db,
            CompanyJobCollectionRequest(company_name=company.name, limit=segment.job_limit),
        )
        if collection.status == "error":
            raise RuntimeError(collection.message or "Company collection failed")
        return {
            "fetched": collection.fetched,
            "created": collection.saved,
            "updated": 0,
            "enriched": collection.fetched,
            "failed": 0,
        }

    if segment.source != JobSource.LINKEDIN or not segment.query:
        raise RuntimeError(f"Unsupported scheduled source: {segment.source}")

    date_posted = segment.initial_date_posted if segment.last_success_at is None else segment.incremental_date_posted
    collection = collect_jobs(
        db,
        JobCollectionRequest(
            sources=[JobSource.LINKEDIN],
            query=segment.query,
            location=segment.location,
            job_board_limit=segment.job_limit,
            date_posted=date_posted,
            linkedin_enrich_details=True,
            linkedin_detail_limit=segment.job_limit,
            include_default_career_pages=False,
        ),
    )
    source_result = collection.results[0]
    if source_result.status == "error":
        raise RuntimeError(source_result.message or "LinkedIn collection failed")
    return {
        "fetched": source_result.fetched,
        "created": source_result.created,
        "updated": source_result.updated,
        "enriched": source_result.enriched,
        "failed": source_result.enrichment_failed,
    }
