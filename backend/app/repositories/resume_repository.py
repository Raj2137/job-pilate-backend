"""Persistence helpers for user resumes."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.resume import UserResume
from app.schemas.resume import UserResumeUpsert


def get_user_resume(db: Session, user_id: int) -> UserResume | None:
    return db.query(UserResume).filter(UserResume.user_id == user_id).first()


def upsert_user_resume(db: Session, *, user_id: int, payload: UserResumeUpsert) -> UserResume:
    resume_text = payload.resume_text.strip()
    resume = get_user_resume(db, user_id)
    now = datetime.now(UTC)
    if resume is None:
        resume = UserResume(
            user_id=user_id,
            resume_text=resume_text,
            filename=payload.filename,
            content_type=payload.content_type,
            character_count=len(resume_text),
            created_at=now,
            updated_at=now,
        )
        db.add(resume)
    else:
        resume.resume_text = resume_text
        resume.filename = payload.filename
        resume.content_type = payload.content_type
        resume.character_count = len(resume_text)
        resume.updated_at = now
    db.commit()
    db.refresh(resume)
    return resume


def delete_user_resume(db: Session, *, user_id: int) -> bool:
    resume = get_user_resume(db, user_id)
    if resume is None:
        return False
    db.delete(resume)
    db.commit()
    return True
