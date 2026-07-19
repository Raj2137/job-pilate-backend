"""User-reviewed application-assistance routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.application import (
    ApplicationPrepareRequest,
    ApplicationProfileRead,
    ApplicationProfileUpdate,
    ApplicationStatusUpdate,
    JobApplicationRead,
)
from app.services.application_service import (
    change_application_status,
    get_applications,
    load_profile,
    prepare_application,
    save_profile,
)


router = APIRouter()


@router.get("/profile", response_model=ApplicationProfileRead | None)
def get_application_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApplicationProfileRead | None:
    return load_profile(db, current_user)


@router.put("/profile", response_model=ApplicationProfileRead)
def update_application_profile(
    payload: ApplicationProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApplicationProfileRead:
    return save_profile(db, current_user, payload)


@router.post("/prepare", response_model=JobApplicationRead)
def prepare_job_application(
    payload: ApplicationPrepareRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobApplicationRead:
    try:
        return prepare_application(db, current_user, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[JobApplicationRead])
def list_user_applications(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[JobApplicationRead]:
    return get_applications(db, current_user, limit=limit)


@router.patch("/{application_id}/status", response_model=JobApplicationRead)
def update_job_application_status(
    application_id: int,
    payload: ApplicationStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobApplicationRead:
    try:
        return change_application_status(db, current_user, application_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
