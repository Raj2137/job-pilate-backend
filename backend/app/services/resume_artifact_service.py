"""Generate, render, persist, and retrieve job-specific resume artifacts."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.models.tailored_resume import TailoredResume
from app.models.user import User
from app.repositories.resume_repository import get_user_resume
from app.repositories.tailored_resume_repository import (
    create_tailored_resume,
    get_tailored_resume,
    list_tailored_resumes,
)
from app.schemas.resume import TailoredResumeRead, TailoredResumeRequest
from app.services.resume_document_service import render_resume_docx, render_resume_in_original_docx
from app.services.resume_source_service import DOCX_CONTENT_TYPE, load_original_resume_file
from app.services.resume_tailoring_service import tailor_resume_for_job
from app.services.resume_tailoring_service import ResumeTailoringValidationError
from app.storage.resume_storage import load_resume_file, prepare_resume_file


def generate_and_save_tailored_resume(
    db: Session,
    *,
    user: User,
    payload: TailoredResumeRequest,
) -> TailoredResumeRead:
    saved_resume = get_user_resume(db, user.id)
    can_preserve_original = bool(
        payload.resume_text is None
        and saved_resume is not None
        and saved_resume.content_type == DOCX_CONTENT_TYPE
        and saved_resume.original_storage_provider
    )
    if payload.render_mode == "original" and not can_preserve_original:
        raise ResumeTailoringValidationError(
            "Original-template mode requires a saved DOCX uploaded through /api/resumes/me/file."
        )
    use_original = payload.render_mode == "original" or (
        payload.render_mode == "auto" and can_preserve_original
    )
    original_file = load_original_resume_file(saved_resume) if use_original else None
    generated = tailor_resume_for_job(db, user=user, payload=payload)
    next_version = _next_version(db, user_id=user.id, job_id=generated.job_id)
    filename = _filename(generated.company, generated.job_title, next_version)
    if use_original:
        file_data = render_resume_in_original_docx(
            original_file,
            generated.tailored_resume_markdown,
        )
        actual_render_mode = "original_docx"
        template_fidelity = "best_effort"
    else:
        file_data = render_resume_docx(generated.tailored_resume_markdown)
        actual_render_mode = "ats"
        template_fidelity = "standardized"
    stored = prepare_resume_file(
        user_id=user.id,
        filename=filename,
        data=file_data,
        category="tailored",
    )
    record = create_tailored_resume(
        db,
        user_id=user.id,
        generated=generated,
        filename=filename,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        file_data=file_data,
        storage_provider=stored.provider,
        storage_key=stored.key,
        requested_render_mode=payload.render_mode,
        actual_render_mode=actual_render_mode,
        template_fidelity=template_fidelity,
    )
    return tailored_resume_read(record)


def get_saved_tailored_resume(db: Session, *, user_id: int, resume_id: int) -> TailoredResume | None:
    return get_tailored_resume(db, user_id=user_id, resume_id=resume_id)


def list_saved_tailored_resumes(db: Session, *, user_id: int, limit: int) -> list[TailoredResumeRead]:
    return [
        tailored_resume_read(record)
        for record in list_tailored_resumes(db, user_id=user_id, limit=limit)
    ]


def tailored_resume_read(record: TailoredResume) -> TailoredResumeRead:
    return TailoredResumeRead(
        id=record.id,
        user_id=record.user_id,
        job_id=record.job_id,
        job_title=record.job_title,
        company=record.company,
        source_resume_id=record.source_resume_id,
        version=record.version,
        tailored_resume_markdown=record.tailored_resume_markdown,
        headline=record.headline,
        professional_summary=record.professional_summary,
        core_skills=record.core_skills,
        keywords_incorporated=record.keywords_incorporated,
        unsupported_job_requirements=record.unsupported_job_requirements,
        change_summary=record.change_summary,
        truthfulness_warnings=record.truthfulness_warnings,
        estimated_alignment_score=record.estimated_alignment_score,
        provider=record.llm_provider,
        model=record.llm_model,
        filename=record.filename,
        content_type=record.content_type,
        file_size=record.file_size,
        storage_provider=record.storage_provider,
        requested_render_mode=record.requested_render_mode,
        actual_render_mode=record.actual_render_mode,
        template_fidelity=record.template_fidelity,
        pdf_render_mode="ats",
        download_url=f"/api/resumes/tailored/{record.id}/download",
        pdf_download_url=f"/api/resumes/tailored/{record.id}/download?format=pdf",
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def tailored_resume_file(record: TailoredResume) -> bytes:
    return load_resume_file(record)


def _next_version(db: Session, *, user_id: int, job_id: int) -> int:
    records = list_tailored_resumes(db, user_id=user_id, limit=1000)
    versions = [record.version for record in records if record.job_id == job_id]
    return max(versions, default=0) + 1


def _filename(company: str, job_title: str, version: int) -> str:
    stem = re.sub(r"[^a-zA-Z0-9]+", "-", f"{company}-{job_title}").strip("-").lower()
    return f"{stem[:180] or 'tailored-resume'}-v{version}.docx"
