"""Small encryption helpers for user-owned secrets."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import get_settings


def _fernet() -> Fernet:
    settings = get_settings()
    secret = settings.llm_key_encryption_secret or settings.secret_key
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")


def key_preview(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) <= 8:
        return "****"
    return f"{cleaned[:4]}...{cleaned[-4:]}"
