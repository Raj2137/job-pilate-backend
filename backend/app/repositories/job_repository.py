"""Job persistence and search helpers."""

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.job import Job
from app.schemas.job import JobCreate


def upsert_job(db: Session, payload: JobCreate) -> Job:
    job = db.query(Job).filter(Job.source == payload.source, Job.external_id == payload.external_id).first()
    values = payload.model_dump()
    values["apply_url"] = str(payload.apply_url) if payload.apply_url else None
    values["source_url"] = str(payload.source_url) if payload.source_url else None

    if job is None:
        job = Job(**values)
        db.add(job)
    else:
        for key, value in values.items():
            setattr(job, key, value)

    db.commit()
    db.refresh(job)
    return job


def search_jobs(
    db: Session,
    *,
    query: str | None = None,
    location: str | None = None,
    source: str | None = None,
    remote: bool | None = None,
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

    total = stmt.count()
    jobs = stmt.order_by(Job.posted_at.desc().nullslast(), Job.created_at.desc()).offset(offset).limit(limit).all()
    return total, jobs
