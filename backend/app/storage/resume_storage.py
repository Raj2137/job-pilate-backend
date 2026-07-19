"""Storage boundary for generated resume files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
class ResumeStorageError(Exception):
    """Raised when resume artifact storage fails."""


@dataclass(frozen=True)
class StoredFile:
    provider: str
    key: str
    data: bytes


def prepare_resume_file(
    *,
    user_id: int,
    filename: str,
    data: bytes,
    category: str = "tailored",
) -> StoredFile:
    settings = get_settings()
    provider = settings.resume_storage_provider.strip().lower()
    key = f"users/{user_id}/resumes/{category}/{filename}"
    if provider == "database":
        return StoredFile(provider="database", key=key, data=data)
    if provider == "local":
        root = Path(settings.resume_storage_path).resolve()
        path = (root / key).resolve()
        if root not in path.parents:
            raise ResumeStorageError("Invalid local resume storage path.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredFile(provider="local", key=key, data=b"")
    raise ResumeStorageError(
        f"Unsupported resume storage provider '{provider}'. Configure 'database' or 'local'."
    )


def load_resume_file(record) -> bytes:
    provider = getattr(record, "storage_provider", None) or getattr(record, "original_storage_provider", None)
    file_data = getattr(record, "file_data", None)
    if file_data is None:
        file_data = getattr(record, "original_file_data", None)
    storage_key = getattr(record, "storage_key", None) or getattr(record, "original_storage_key", None)
    if provider == "database":
        if file_data is None:
            raise ResumeStorageError("Stored resume file is missing.")
        return bytes(file_data)
    if provider == "local":
        root = Path(get_settings().resume_storage_path).resolve()
        path = (root / storage_key).resolve()
        if root not in path.parents or not path.is_file():
            raise ResumeStorageError("Stored resume file is missing.")
        return path.read_bytes()
    raise ResumeStorageError(f"Unsupported stored resume provider '{provider}'.")
