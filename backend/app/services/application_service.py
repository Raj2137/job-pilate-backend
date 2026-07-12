"""Prepare user-reviewed application field plans."""

from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.user import User
from app.repositories.application_repository import (
    create_job_application,
    get_application_profile,
    get_job_application,
    list_job_applications,
    update_application_status,
    upsert_application_profile,
)
from app.schemas.application import ApplicationPrepareRequest, ApplicationProfileUpdate, ApplicationStatusUpdate


ALLOWED_TRANSITIONS = {
    "draft": {"ready_for_review", "opened", "failed"},
    "ready_for_review": {"opened", "submitted", "failed"},
    "opened": {"ready_for_review", "submitted", "failed"},
    "failed": {"ready_for_review", "opened"},
    "submitted": set(),
}


def save_profile(db: Session, user: User, payload: ApplicationProfileUpdate):
    return upsert_application_profile(db, user_id=user.id, payload=payload)


def load_profile(db: Session, user: User):
    return get_application_profile(db, user.id)


def prepare_application(db: Session, user: User, payload: ApplicationPrepareRequest):
    job = db.get(Job, payload.job_id)
    if job is None:
        raise LookupError("Job not found")
    profile = get_application_profile(db, user.id)
    if profile is None:
        raise ValueError("Application profile must be completed first")

    first_name, last_name = _split_name(user.full_name)
    fields = {
        "first_name": first_name,
        "last_name": last_name,
        "email": user.email,
        "phone": profile.phone,
        "current_location": profile.current_location,
        "linkedin_url": profile.linkedin_url,
        "portfolio_url": profile.portfolio_url,
        "github_url": profile.github_url,
        "resume_url": profile.resume_url,
        "years_experience": profile.years_experience,
        "work_authorization": profile.work_authorization,
        "requires_sponsorship": profile.requires_sponsorship,
        **(profile.default_answers or {}),
        **payload.overrides,
    }
    fields = {key: value for key, value in fields.items() if value is not None and value != ""}
    required = ("first_name", "last_name", "email", "phone", "current_location", "resume_url")
    missing = [field for field in required if not fields.get(field)]
    status = "ready_for_review" if not missing else "draft"
    mode = "assisted" if job.apply_url else "manual"
    return create_job_application(
        db,
        user_id=user.id,
        job_id=job.id,
        status=status,
        mode=mode,
        apply_url=job.apply_url,
        field_values=fields,
        missing_fields=missing,
    )


def change_application_status(
    db: Session,
    user: User,
    application_id: int,
    payload: ApplicationStatusUpdate,
):
    application = get_job_application(db, application_id=application_id, user_id=user.id)
    if application is None:
        raise LookupError("Application not found")
    if payload.status not in ALLOWED_TRANSITIONS.get(application.status, set()):
        raise ValueError(f"Cannot move application from {application.status} to {payload.status}")
    if payload.status == "submitted" and not payload.user_confirmed:
        raise ValueError("User confirmation is required before marking an application submitted")
    if payload.status in {"ready_for_review", "submitted"} and application.missing_fields:
        raise ValueError("Required application fields are still missing")
    return update_application_status(
        db,
        application,
        status=payload.status,
        user_confirmed=payload.user_confirmed,
        error=payload.error,
    )


def get_applications(db: Session, user: User, *, limit: int):
    return list_job_applications(db, user_id=user.id, limit=limit)


def _split_name(full_name: str | None) -> tuple[str | None, str | None]:
    if not full_name:
        return None, None
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " ".join(parts[1:])
