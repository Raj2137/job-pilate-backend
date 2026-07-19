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
            original_file_size=None,
            original_file_sha256=None,
            original_storage_provider=None,
            original_storage_key=None,
            original_file_data=None,
            created_at=now,
            updated_at=now,
        )
        db.add(resume)
    else:
        resume.resume_text = resume_text
        resume.filename = payload.filename
        resume.content_type = payload.content_type
        resume.character_count = len(resume_text)
        resume.original_file_size = None
        resume.original_file_sha256 = None
        resume.original_storage_provider = None
        resume.original_storage_key = None
        resume.original_file_data = None
        resume.updated_at = now
    db.commit()
    db.refresh(resume)
    return resume


def upsert_user_resume_file(
    db: Session,
    *,
    user_id: int,
    resume_text: str,
    filename: str,
    content_type: str,
    file_data: bytes,
    file_sha256: str,
    storage_provider: str,
    storage_key: str,
) -> UserResume:
    resume = get_user_resume(db, user_id)
    now = datetime.now(UTC)
    values = {
        "resume_text": resume_text.strip(),
        "filename": filename,
        "content_type": content_type,
        "character_count": len(resume_text.strip()),
        "original_file_size": len(file_data),
        "original_file_sha256": file_sha256,
        "original_storage_provider": storage_provider,
        "original_storage_key": storage_key,
        "original_file_data": file_data if storage_provider == "database" else None,
        "updated_at": now,
    }
    if resume is None:
        resume = UserResume(user_id=user_id, created_at=now, **values)
        db.add(resume)
    else:
        for name, value in values.items():
            setattr(resume, name, value)
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
