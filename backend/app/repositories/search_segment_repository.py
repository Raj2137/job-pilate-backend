"""Persistence and leasing for scheduled collection targets."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.search_segment import CollectionRun, SearchSegment
from app.providers.sources import JobSource
from app.schemas.search_segment import SearchSegmentCreate


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def ensure_linkedin_segment(db: Session, payload: SearchSegmentCreate) -> SearchSegment:
    query = _normalize(payload.query or "")
    location = _normalize(payload.location or "") or None
    key = _segment_key(JobSource.LINKEDIN, query, location)
    segment = db.query(SearchSegment).filter(SearchSegment.key == key).first()
    now = utc_now()

    if segment is None:
        segment = SearchSegment(
            key=key,
            source=JobSource.LINKEDIN,
            query=query,
            location=location,
            interval_minutes=payload.interval_minutes,
            job_limit=payload.job_limit,
            initial_date_posted=payload.initial_date_posted,
            incremental_date_posted=payload.incremental_date_posted,
            priority=payload.priority,
            is_active=True,
            status="pending",
            next_run_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(segment)
    else:
        segment.interval_minutes = payload.interval_minutes
        segment.job_limit = payload.job_limit
        segment.initial_date_posted = payload.initial_date_posted
        segment.incremental_date_posted = payload.incremental_date_posted
        segment.priority = payload.priority
        segment.is_active = True
        segment.updated_at = now
        if segment.status == "paused":
            segment.status = "pending"
            segment.next_run_at = now

    db.commit()
    db.refresh(segment)
    return segment


def ensure_company_segments(
    db: Session,
    *,
    interval_minutes: int = 60,
    company_ids: set[int] | None = None,
    ats_types: set[str] | None = None,
    job_limit: int = 500,
) -> int:
    query = db.query(Company).filter(Company.is_active.is_(True))
    if company_ids is not None:
        query = query.filter(Company.id.in_(company_ids))
    if ats_types is not None:
        query = query.filter(Company.ats_type.in_(ats_types))
    companies = query.all()
    existing = {
        segment.company_id: segment
        for segment in db.query(SearchSegment).filter(SearchSegment.company_id.is_not(None)).all()
    }
    now = utc_now()
    created = 0
    for company in companies:
        supported = company.ats_type in {"greenhouse", "lever", "ashby", "smartrecruiters", "workday"}
        company_interval = interval_minutes if supported else max(interval_minutes, 240)
        if company.id in existing:
            segment = existing[company.id]
            segment.interval_minutes = company_interval
            segment.job_limit = job_limit
            segment.priority = 50 if supported else 200
            segment.updated_at = now
            continue
        db.add(
            SearchSegment(
                key=f"company:{company.id}",
                source=JobSource.CAREER_PAGES,
                query=company.name,
                company_id=company.id,
                interval_minutes=company_interval,
                job_limit=job_limit,
                priority=50 if supported else 200,
                is_active=True,
                status="pending",
                next_run_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        created += 1
    db.commit()
    return created


def list_segments(db: Session, *, active_only: bool = False) -> tuple[int, list[SearchSegment]]:
    query = db.query(SearchSegment)
    if active_only:
        query = query.filter(SearchSegment.is_active.is_(True))
    return query.count(), query.order_by(SearchSegment.priority.asc(), SearchSegment.created_at.asc()).all()


def get_segment(db: Session, segment_id: int) -> SearchSegment | None:
    return db.query(SearchSegment).filter(SearchSegment.id == segment_id).first()


def list_runs(db: Session, *, segment_id: int, limit: int = 20) -> list[CollectionRun]:
    return (
        db.query(CollectionRun)
        .filter(CollectionRun.segment_id == segment_id)
        .order_by(CollectionRun.started_at.desc())
        .limit(limit)
        .all()
    )


def claim_due_segments(
    db: Session,
    *,
    worker_id: str,
    limit: int,
    lease_minutes: int,
) -> list[SearchSegment]:
    now = utc_now()
    query = (
        db.query(SearchSegment)
        .filter(
            SearchSegment.is_active.is_(True),
            SearchSegment.next_run_at <= now,
            or_(SearchSegment.lease_expires_at.is_(None), SearchSegment.lease_expires_at <= now),
        )
        .order_by(SearchSegment.priority.asc(), SearchSegment.next_run_at.asc())
    )
    if db.get_bind().dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    segments = query.limit(limit).all()
    for segment in segments:
        segment.status = "running"
        segment.last_started_at = now
        segment.lease_owner = worker_id
        segment.lease_expires_at = now + timedelta(minutes=lease_minutes)
        segment.updated_at = now
    db.commit()
    return segments


def begin_run(db: Session, segment: SearchSegment) -> CollectionRun:
    run = CollectionRun(
        segment_id=segment.id,
        source=segment.source,
        status="running",
        started_at=utc_now(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def complete_run(
    db: Session,
    *,
    segment: SearchSegment,
    run: CollectionRun,
    fetched: int,
    created: int,
    updated: int,
    enriched: int,
    failed: int,
) -> None:
    now = utc_now()
    run.status = "completed"
    run.completed_at = now
    run.fetched = fetched
    run.created = created
    run.updated = updated
    run.enriched = enriched
    run.failed = failed
    segment.status = "ready"
    segment.last_success_at = now
    segment.next_run_at = now + timedelta(minutes=segment.interval_minutes)
    segment.lease_owner = None
    segment.lease_expires_at = None
    segment.last_error = None
    segment.run_count += 1
    segment.updated_at = now
    db.commit()


def fail_run(db: Session, *, segment: SearchSegment, run: CollectionRun, error: str) -> None:
    now = utc_now()
    message = error[:2000]
    run.status = "failed"
    run.completed_at = now
    run.error = message
    segment.status = "error"
    segment.last_error = message
    segment.next_run_at = now + timedelta(minutes=min(segment.interval_minutes, 15))
    segment.lease_owner = None
    segment.lease_expires_at = None
    segment.updated_at = now
    db.commit()


def make_segment_due(db: Session, segment: SearchSegment) -> SearchSegment:
    segment.is_active = True
    segment.status = "pending"
    segment.next_run_at = utc_now()
    segment.lease_owner = None
    segment.lease_expires_at = None
    segment.updated_at = utc_now()
    db.commit()
    db.refresh(segment)
    return segment


def pause_segment(db: Session, segment: SearchSegment) -> SearchSegment:
    segment.is_active = False
    segment.status = "paused"
    segment.lease_owner = None
    segment.lease_expires_at = None
    segment.updated_at = utc_now()
    db.commit()
    db.refresh(segment)
    return segment


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _segment_key(source: JobSource, query: str, location: str | None) -> str:
    canonical = f"{source.value}|{query}|{location or ''}"
    return f"{source.value}:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"
