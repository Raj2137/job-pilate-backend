"""Persistence helpers for user-assisted applications."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.application import ApplicationProfile, JobApplication
from app.schemas.application import ApplicationProfileUpdate


def get_application_profile(db: Session, user_id: int) -> ApplicationProfile | None:
    return db.query(ApplicationProfile).filter(ApplicationProfile.user_id == user_id).first()


def upsert_application_profile(
    db: Session,
    *,
    user_id: int,
    payload: ApplicationProfileUpdate,
) -> ApplicationProfile:
    profile = get_application_profile(db, user_id)
    values = payload.model_dump()
    for field in ("linkedin_url", "portfolio_url", "github_url", "resume_url"):
        value = getattr(payload, field)
        values[field] = str(value) if value else None
    if profile is None:
        profile = ApplicationProfile(user_id=user_id, **values)
        db.add(profile)
    else:
        for key, value in values.items():
            setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    return profile


def create_job_application(
    db: Session,
    *,
    user_id: int,
    job_id: int,
    status: str,
    mode: str,
    apply_url: str | None,
    field_values: dict,
    missing_fields: list[str],
) -> JobApplication:
    application = JobApplication(
        user_id=user_id,
        job_id=job_id,
        status=status,
        mode=mode,
        apply_url=apply_url,
        field_values=field_values,
        missing_fields=missing_fields,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


def get_job_application(db: Session, *, application_id: int, user_id: int) -> JobApplication | None:
    return (
        db.query(JobApplication)
        .filter(JobApplication.id == application_id, JobApplication.user_id == user_id)
        .first()
    )


def list_job_applications(db: Session, *, user_id: int, limit: int = 100) -> list[JobApplication]:
    return (
        db.query(JobApplication)
        .filter(JobApplication.user_id == user_id)
        .order_by(JobApplication.created_at.desc())
        .limit(limit)
        .all()
    )


def update_application_status(
    db: Session,
    application: JobApplication,
    *,
    status: str,
    user_confirmed: bool,
    error: str | None,
) -> JobApplication:
    application.status = status
    application.user_confirmed = user_confirmed
    application.error = error
    if status == "submitted":
        application.submitted_at = datetime.now(UTC)
    db.commit()
    db.refresh(application)
    return application
