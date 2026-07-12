"""Schemas for user-owned LLM provider keys."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class LlmProvider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    GROQ = "groq"
    OPENROUTER = "openrouter"


DEFAULT_MODEL_BY_PROVIDER = {
    LlmProvider.OPENAI: "gpt-4o-mini",
    LlmProvider.ANTHROPIC: "claude-3-5-haiku-latest",
    LlmProvider.GEMINI: "gemini-1.5-flash",
    LlmProvider.GROQ: "qwen/qwen3-32b",
    LlmProvider.OPENROUTER: "qwen/qwen3-32b",
}


class LlmKeyCreate(BaseModel):
    provider: LlmProvider
    api_key: str = Field(min_length=8)
    label: str | None = Field(default=None, max_length=100)
    default_model: str | None = Field(default=None, max_length=255)
    is_active: bool = True


class LlmKeyUpdate(BaseModel):
    api_key: str | None = Field(default=None, min_length=8)
    label: str | None = Field(default=None, max_length=100)
    default_model: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class LlmKeyRead(BaseModel):
    id: int
    provider: LlmProvider
    label: str
    key_preview: str
    default_model: str | None
    is_active: bool
    has_key: bool = True
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LlmKeyTestResponse(BaseModel):
    status: str
    provider: LlmProvider
    model: str | None
    message: str
