"""Job persistence and search helpers."""

from datetime import datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.job import Job
from app.schemas.job import JobCreate


def upsert_job(db: Session, payload: JobCreate) -> Job:
    job = db.query(Job).filter(Job.source == payload.source, Job.external_id == payload.external_id).first()
    values = _job_values(payload)

    if job is None:
        job = Job(**values)
        db.add(job)
    else:
        for key, value in values.items():
            if value is not None:
                setattr(job, key, value)
        if payload.details_status == "complete":
            job.details_error = None

    db.commit()
    db.refresh(job)
    return job


def get_jobs_by_external_ids(db: Session, *, source: str, external_ids: list[str]) -> dict[str, Job]:
    jobs: dict[str, Job] = {}
    for start in range(0, len(external_ids), 500):
        chunk = external_ids[start : start + 500]
        if not chunk:
            continue
        rows = db.query(Job).filter(Job.source == source, Job.external_id.in_(chunk)).all()
        jobs.update({row.external_id: row for row in rows})
    return jobs


def upsert_jobs(db: Session, payloads: list[JobCreate]) -> tuple[int, int]:
    if not payloads:
        return 0, 0

    existing_by_source: dict[str, dict[str, Job]] = {}
    for source in {payload.source for payload in payloads}:
        external_ids = [payload.external_id for payload in payloads if payload.source == source]
        existing_by_source[source] = get_jobs_by_external_ids(db, source=source, external_ids=external_ids)

    created = 0
    updated = 0
    for payload in payloads:
        values = _job_values(payload)
        job = existing_by_source[payload.source].get(payload.external_id)

        if job is None:
            job = Job(**values)
            db.add(job)
            existing_by_source[payload.source][payload.external_id] = job
            created += 1
        else:
            for key, value in values.items():
                if value is not None:
                    setattr(job, key, value)
            if payload.details_status == "complete":
                job.details_error = None
            updated += 1

    db.commit()
    return created, updated


def list_linkedin_jobs_needing_enrichment(db: Session, *, limit: int) -> list[Job]:
    return (
        db.query(Job)
        .filter(Job.source == "linkedin", Job.description.is_(None))
        .order_by(Job.details_attempts.asc(), Job.posted_at.desc().nullslast(), Job.created_at.desc())
        .limit(limit)
        .all()
    )


def count_linkedin_jobs_needing_enrichment(db: Session) -> int:
    return db.query(Job).filter(Job.source == "linkedin", Job.description.is_(None)).count()


def list_job_filter_options(db: Session, *, top_limit: int = 100) -> dict:
    return {
        "total_jobs": db.query(Job).count(),
        "jobs_with_jd": db.query(Job).filter(Job.description.is_not(None)).count(),
        "jobs_without_jd": db.query(Job).filter(Job.description.is_(None)).count(),
        "sources": _facet_counts(db, Job.source, top_limit),
        "companies": _facet_counts(db, Job.company, top_limit),
        "locations": _facet_counts(db, Job.location, top_limit),
        "employment_types": _facet_counts(db, Job.employment_type, top_limit),
        "application_methods": _facet_counts(db, Job.application_method, top_limit),
        "details_statuses": _facet_counts(db, Job.details_status, top_limit),
        "remote": [
            {"value": "true", "count": db.query(Job).filter(Job.remote.is_(True)).count()},
            {"value": "false", "count": db.query(Job).filter(Job.remote.is_(False)).count()},
        ],
    }


def list_match_candidates(
    db: Session,
    *,
    query_terms: list[str],
    job_title: str | None,
    companies: list[str],
    preferred_locations: list[str],
    remote: bool | None,
    source: str | None,
    posted_since: datetime | None,
    require_jd: bool,
    latest_first: bool,
    limit: int,
) -> list[Job]:
    stmt = db.query(Job)

    if job_title:
        title_terms = _search_terms(job_title)
        title_clauses = []
        for term in title_terms:
            pattern = f"%{term}%"
            title_clauses.extend([Job.title.ilike(pattern), Job.description.ilike(pattern)])
        if title_clauses:
            stmt = stmt.filter(or_(*title_clauses))

    if query_terms:
        clauses = []
        for term in query_terms[:20]:
            pattern = f"%{term.strip()}%"
            clauses.extend(
                [
                    Job.title.ilike(pattern),
                    Job.company.ilike(pattern),
                    Job.description.ilike(pattern),
                ]
            )
        stmt = stmt.filter(or_(*clauses))

    if preferred_locations:
        location_clauses = [Job.location.ilike(f"%{location.strip()}%") for location in preferred_locations]
        stmt = stmt.filter(or_(*location_clauses))

    if companies:
        company_clauses = [Job.company.ilike(f"%{company.strip()}%") for company in companies if company.strip()]
        if company_clauses:
            stmt = stmt.filter(or_(*company_clauses))

    if remote is not None:
        stmt = stmt.filter(Job.remote == remote)

    if source:
        stmt = stmt.filter(Job.source == source)

    if posted_since is not None:
        stmt = stmt.filter(or_(Job.posted_at >= posted_since, Job.posted_at.is_(None)))

    if require_jd:
        stmt = stmt.filter(Job.description.is_not(None))

    if latest_first:
        stmt = stmt.order_by(Job.posted_at.desc().nullslast(), Job.created_at.desc())
    else:
        stmt = stmt.order_by(Job.created_at.desc())
    return stmt.limit(limit).all()


def _search_terms(value: str) -> list[str]:
    normalized = value.strip().lower().replace("-", " ")
    terms = [term for term in normalized.split() if len(term) > 2]
    if "developer" in terms:
        terms.append("engineer")
    if "engineer" in terms:
        terms.append("developer")
    if "full" in terms and "stack" in terms:
        terms.append("fullstack")
    return list(dict.fromkeys(terms))


def _facet_counts(db: Session, column, limit: int) -> list[dict[str, int | str]]:
    rows = (
        db.query(column.label("value"), func.count(Job.id).label("count"))
        .filter(column.is_not(None), column != "")
        .group_by(column)
        .order_by(func.count(Job.id).desc(), column.asc())
        .limit(limit)
        .all()
    )
    return [{"value": str(row.value), "count": int(row.count)} for row in rows]


def _job_values(payload: JobCreate) -> dict:
    values = payload.model_dump()
    for field in ("apply_url", "source_url", "company_url"):
        value = getattr(payload, field)
        values[field] = str(value) if value else None
    if values.get("details_attempts") is None:
        values.pop("details_attempts")
    return values


def search_jobs(
    db: Session,
    *,
    query: str | None = None,
    location: str | None = None,
    source: str | None = None,
    remote: bool | None = None,
    application_method: str | None = None,
    details_status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[int, list[Job]]:
    stmt = db.query(Job)

    if query:
        pattern = f"%{query.strip()}%"
        stmt = stmt.filter(
            or_(
                Job.title.ilike(pattern),
                Job.company.ilike(pattern),
                Job.description.ilike(pattern),
            )
        )

    if location:
        stmt = stmt.filter(Job.location.ilike(f"%{location.strip()}%"))

    if source:
        stmt = stmt.filter(Job.source == source)

    if remote is not None:
        stmt = stmt.filter(Job.remote == remote)

    if application_method:
        stmt = stmt.filter(Job.application_method == application_method)

    if details_status:
        stmt = stmt.filter(Job.details_status == details_status)

    total = stmt.count()
    jobs = stmt.order_by(Job.posted_at.desc().nullslast(), Job.created_at.desc()).offset(offset).limit(limit).all()
    return total, jobs


def search_jobs_by_company(
    db: Session,
    *,
    company: str,
    query: str | None = None,
    location: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, list[Job]]:
    stmt = db.query(Job).filter(Job.company.ilike(f"%{company.strip()}%"))

    if query:
        pattern = f"%{query.strip()}%"
        stmt = stmt.filter(
            or_(
                Job.title.ilike(pattern),
                Job.description.ilike(pattern),
            )
        )

    if location:
        stmt = stmt.filter(Job.location.ilike(f"%{location.strip()}%"))

    total = stmt.count()
    jobs = stmt.order_by(Job.posted_at.desc().nullslast(), Job.created_at.desc()).offset(offset).limit(limit).all()
    return total, jobs
