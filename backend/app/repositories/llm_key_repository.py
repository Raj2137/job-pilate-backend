"""Persistence helpers for user-owned LLM keys."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.encryption import decrypt_secret, encrypt_secret, key_preview
from app.models.llm_key import UserLlmKey
from app.models.user import User
from app.schemas.llm_key import DEFAULT_MODEL_BY_PROVIDER, LlmKeyCreate, LlmKeyUpdate


def list_llm_keys(db: Session, user: User) -> list[UserLlmKey]:
    return (
        db.query(UserLlmKey)
        .filter(UserLlmKey.user_id == user.id)
        .order_by(UserLlmKey.created_at.desc())
        .all()
    )


def get_llm_key(db: Session, user: User, key_id: int) -> UserLlmKey | None:
    return db.query(UserLlmKey).filter(UserLlmKey.user_id == user.id, UserLlmKey.id == key_id).first()


def get_default_llm_key(db: Session, user: User) -> UserLlmKey | None:
    return (
        db.query(UserLlmKey)
        .filter(UserLlmKey.user_id == user.id, UserLlmKey.is_active.is_(True))
        .order_by(UserLlmKey.updated_at.desc(), UserLlmKey.id.desc())
        .first()
    )


def create_llm_key(db: Session, user: User, payload: LlmKeyCreate) -> UserLlmKey:
    raw_key = payload.api_key.strip()
    provider = payload.provider.value
    label = payload.label or payload.provider.value.title()
    model = payload.default_model or DEFAULT_MODEL_BY_PROVIDER[payload.provider]
    record = UserLlmKey(
        user_id=user.id,
        provider=provider,
        label=label,
        encrypted_api_key=encrypt_secret(raw_key),
        key_preview=key_preview(raw_key),
        default_model=model,
        is_active=payload.is_active,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update_llm_key(db: Session, record: UserLlmKey, payload: LlmKeyUpdate) -> UserLlmKey:
    if payload.api_key is not None:
        raw_key = payload.api_key.strip()
        record.encrypted_api_key = encrypt_secret(raw_key)
        record.key_preview = key_preview(raw_key)
    if payload.label is not None:
        record.label = payload.label
    if payload.default_model is not None:
        record.default_model = payload.default_model
    if payload.is_active is not None:
        record.is_active = payload.is_active
    db.commit()
    db.refresh(record)
    return record


def delete_llm_key(db: Session, record: UserLlmKey) -> None:
    db.delete(record)
    db.commit()


def decrypt_llm_key(record: UserLlmKey) -> str:
    return decrypt_secret(record.encrypted_api_key)


def mark_llm_key_used(db: Session, record: UserLlmKey) -> None:
    record.last_used_at = datetime.now(UTC)
    db.commit()
