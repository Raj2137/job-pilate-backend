"""Authenticated resume routes."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import get_db
from app.models.resume import UserResume
from app.models.user import User
from app.repositories.resume_repository import delete_user_resume, get_user_resume, upsert_user_resume
from app.schemas.resume import UserResumeRead, UserResumeStatus, UserResumeUpsert

router = APIRouter()


def _read_resume(resume: UserResume) -> UserResumeRead:
    text = resume.resume_text
    preview = text[:240].strip()
    if len(text) > len(preview):
        preview = f"{preview}..."
    return UserResumeRead(
        id=resume.id,
        resume_text=text,
        filename=resume.filename,
        content_type=resume.content_type,
        character_count=resume.character_count,
        text_preview=preview,
        created_at=resume.created_at,
        updated_at=resume.updated_at,
    )


@router.get("/me", response_model=UserResumeStatus)
def get_my_resume(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResumeStatus:
    resume = get_user_resume(db, current_user.id)
    if resume is None:
        return UserResumeStatus(has_resume=False)
    return UserResumeStatus(has_resume=True, resume=_read_resume(resume))


@router.post("/me", response_model=UserResumeRead, status_code=status.HTTP_201_CREATED)
def upload_my_resume(
    payload: UserResumeUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResumeRead:
    return _read_resume(upsert_user_resume(db, user_id=current_user.id, payload=payload))


@router.put("/me", response_model=UserResumeRead)
def replace_my_resume(
    payload: UserResumeUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResumeRead:
    return _read_resume(upsert_user_resume(db, user_id=current_user.id, payload=payload))


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_resume(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    delete_user_resume(db, user_id=current_user.id)
