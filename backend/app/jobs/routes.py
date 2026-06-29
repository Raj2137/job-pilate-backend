"""Job search routes."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.repositories.job_repository import search_jobs, upsert_job
from app.schemas.job import JobCreate, JobRead, JobSearchResponse

router = APIRouter()


@router.get("/search", response_model=JobSearchResponse)
def search(
    query: str | None = Query(default=None, description="Search title, company, and description"),
    location: str | None = Query(default=None),
    source: str | None = Query(default=None),
    remote: bool | None = Query(default=None),
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
