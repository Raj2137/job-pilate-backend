"""Persistence helpers for versioned tailored resumes."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.tailored_resume import TailoredResume
from app.schemas.resume import TailoredResumeResponse


def create_tailored_resume(
    db: Session,
    *,
    user_id: int,
    generated: TailoredResumeResponse,
    filename: str,
    content_type: str,
    file_data: bytes,
    storage_provider: str,
    storage_key: str,
    requested_render_mode: str = "auto",
    actual_render_mode: str = "ats",
    template_fidelity: str = "standardized",
) -> TailoredResume:
    latest_version = (
        db.query(func.max(TailoredResume.version))
        .filter(TailoredResume.user_id == user_id, TailoredResume.job_id == generated.job_id)
        .scalar()
        or 0
    )
    record = TailoredResume(
        user_id=user_id,
        job_id=generated.job_id,
        source_resume_id=generated.source_resume_id,
        version=latest_version + 1,
        job_title=generated.job_title,
        company=generated.company,
        tailored_resume_markdown=generated.tailored_resume_markdown,
        headline=generated.headline,
        professional_summary=generated.professional_summary,
        core_skills=generated.core_skills,
        keywords_incorporated=generated.keywords_incorporated,
        unsupported_job_requirements=generated.unsupported_job_requirements,
        change_summary=generated.change_summary,
        truthfulness_warnings=generated.truthfulness_warnings,
        estimated_alignment_score=generated.estimated_alignment_score,
        llm_provider=generated.provider,
        llm_model=generated.model,
        requested_render_mode=requested_render_mode,
        actual_render_mode=actual_render_mode,
        template_fidelity=template_fidelity,
        filename=filename,
        content_type=content_type,
        file_size=len(file_data),
        storage_provider=storage_provider,
        storage_key=storage_key,
        file_data=file_data if storage_provider == "database" else None,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_tailored_resume(db: Session, *, user_id: int, resume_id: int) -> TailoredResume | None:
    return (
        db.query(TailoredResume)
        .filter(TailoredResume.id == resume_id, TailoredResume.user_id == user_id)
        .first()
    )


def list_tailored_resumes(db: Session, *, user_id: int, limit: int = 100) -> list[TailoredResume]:
    return (
        db.query(TailoredResume)
        .filter(TailoredResume.user_id == user_id)
        .order_by(TailoredResume.created_at.desc())
        .limit(limit)
        .all()
    )
