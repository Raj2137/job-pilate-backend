"""User routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.llm_client import LlmProviderError, test_llm_key
from app.auth.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.repositories.llm_key_repository import (
    create_llm_key,
    decrypt_llm_key,
    delete_llm_key,
    get_llm_key,
    list_llm_keys,
    mark_llm_key_used,
    update_llm_key,
)
from app.schemas.llm_key import LlmKeyCreate, LlmKeyRead, LlmKeyTestResponse, LlmKeyUpdate, LlmProvider
from app.schemas.user import UserRead

router = APIRouter()


@router.get("/me", response_model=UserRead)
def read_me(current_user: User = Depends(get_current_user)) -> UserRead:
    return current_user


@router.get("/me/llm-keys", response_model=list[LlmKeyRead])
def get_my_llm_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[LlmKeyRead]:
    return list_llm_keys(db, current_user)


@router.post("/me/llm-keys", response_model=LlmKeyRead)
def add_my_llm_key(
    payload: LlmKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LlmKeyRead:
    return create_llm_key(db, current_user, payload)


@router.patch("/me/llm-keys/{key_id}", response_model=LlmKeyRead)
def update_my_llm_key(
    key_id: int,
    payload: LlmKeyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LlmKeyRead:
    record = get_llm_key(db, current_user, key_id)
    if record is None:
        raise HTTPException(status_code=404, detail="LLM key not found")
    return update_llm_key(db, record, payload)


@router.delete("/me/llm-keys/{key_id}", status_code=204)
def delete_my_llm_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    record = get_llm_key(db, current_user, key_id)
    if record is None:
        raise HTTPException(status_code=404, detail="LLM key not found")
    delete_llm_key(db, record)


@router.post("/me/llm-keys/{key_id}/test", response_model=LlmKeyTestResponse)
def test_my_llm_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LlmKeyTestResponse:
    record = get_llm_key(db, current_user, key_id)
    if record is None:
        raise HTTPException(status_code=404, detail="LLM key not found")
    if not record.is_active:
        raise HTTPException(status_code=409, detail="LLM key is inactive")
    provider = LlmProvider(record.provider)
    try:
        text = test_llm_key(provider=provider, api_key=decrypt_llm_key(record), model=record.default_model or "")
    except LlmProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    mark_llm_key_used(db, record)
    return LlmKeyTestResponse(
        status="ok",
        provider=provider,
        model=record.default_model,
        message=text.strip()[:200] or "ok",
    )
