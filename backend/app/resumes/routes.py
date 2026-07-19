"""Authenticated resume routes."""

from io import BytesIO
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import get_db
from app.models.resume import UserResume
from app.models.user import User
from app.repositories.resume_repository import delete_user_resume, get_user_resume, upsert_user_resume
from app.schemas.resume import (
    TailoredResumeRequest,
    TailoredResumeRead,
    UserResumeRead,
    UserResumeStatus,
    UserResumeUpsert,
)
from app.services.resume_artifact_service import (
    generate_and_save_tailored_resume,
    get_saved_tailored_resume,
    list_saved_tailored_resumes,
    tailored_resume_file,
    tailored_resume_read,
)
from app.services.resume_document_service import render_resume_pdf
from app.services.resume_source_service import (
    MAX_RESUME_FILE_SIZE,
    ResumeSourceError,
    load_original_resume_file,
    save_original_resume,
)
from app.services.resume_tailoring_service import (
    ResumeTailoringNotFoundError,
    ResumeTailoringProviderError,
    ResumeTailoringValidationError,
)
from app.storage.resume_storage import ResumeStorageError

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
        original_file_available=bool(resume.original_storage_provider),
        original_file_size=resume.original_file_size,
        original_file_sha256=resume.original_file_sha256,
        template_capability=(
            "original_docx"
            if resume.original_storage_provider
            and resume.content_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            else "ats_reconstruction"
        ),
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


@router.post("/me/file", response_model=UserResumeRead, status_code=status.HTTP_201_CREATED)
async def upload_my_original_resume_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResumeRead:
    file_data = await file.read(MAX_RESUME_FILE_SIZE + 1)
    try:
        resume = save_original_resume(
            db,
            user_id=current_user.id,
            filename=file.filename or "resume",
            content_type=file.content_type,
            file_data=file_data,
        )
    except ResumeSourceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _read_resume(resume)


@router.get("/me/file")
def download_my_original_resume_file(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    resume = get_user_resume(db, current_user.id)
    if resume is None or not resume.original_storage_provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original resume file not found")
    try:
        file_data = load_original_resume_file(resume)
    except (ResumeSourceError, ResumeStorageError) as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    filename = (resume.filename or "resume").replace('"', "")
    return StreamingResponse(
        BytesIO(file_data),
        media_type=resume.content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_resume(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    delete_user_resume(db, user_id=current_user.id)


@router.post("/tailor", response_model=TailoredResumeRead, status_code=status.HTTP_201_CREATED)
def tailor_my_resume(
    payload: TailoredResumeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TailoredResumeRead:
    try:
        return generate_and_save_tailored_resume(db, user=current_user, payload=payload)
    except ResumeTailoringNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ResumeTailoringValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ResumeTailoringProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except (ResumeStorageError, RuntimeError) as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/tailored", response_model=list[TailoredResumeRead])
def list_my_tailored_resumes(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TailoredResumeRead]:
    return list_saved_tailored_resumes(db, user_id=current_user.id, limit=limit)


@router.get("/tailored/{resume_id}", response_model=TailoredResumeRead)
def get_my_tailored_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TailoredResumeRead:
    record = get_saved_tailored_resume(db, user_id=current_user.id, resume_id=resume_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tailored resume not found")
    return tailored_resume_read(record)


@router.get("/tailored/{resume_id}/download")
def download_my_tailored_resume(
    resume_id: int,
    file_format: Literal["docx", "pdf"] = Query(default="docx", alias="format"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    record = get_saved_tailored_resume(db, user_id=current_user.id, resume_id=resume_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tailored resume not found")
    try:
        if file_format == "pdf":
            file_data = render_resume_pdf(record.tailored_resume_markdown)
            filename = record.filename.rsplit(".", 1)[0] + ".pdf"
            content_type = "application/pdf"
        else:
            file_data = tailored_resume_file(record)
            filename = record.filename
            content_type = record.content_type
    except (ResumeStorageError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return StreamingResponse(
        BytesIO(file_data),
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
