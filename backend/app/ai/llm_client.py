"""Provider connectors for BYOK LLM calls."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import get_settings
from app.schemas.llm_key import LlmProvider


class LlmProviderError(Exception):
    """Raised when a configured LLM provider call fails."""


@dataclass(frozen=True)
class LlmCompletionRequest:
    provider: LlmProvider
    api_key: str
    model: str
    system_prompt: str
    user_prompt: str
    max_tokens: int = 1200
    temperature: float = 0.2


def complete_text(payload: LlmCompletionRequest) -> str:
    if not payload.model.strip() or payload.model.strip().casefold() in {
        "string",
        "model",
        "default",
        "your-model",
        "model-name",
    }:
        raise LlmProviderError(
            "Invalid model configuration. Save a real provider model ID in the selected LLM key."
        )
    if payload.provider in {LlmProvider.OPENAI, LlmProvider.GROQ, LlmProvider.OPENROUTER}:
        return _complete_openai_compatible(payload)
    if payload.provider == LlmProvider.ANTHROPIC:
        return _complete_anthropic(payload)
    if payload.provider == LlmProvider.GEMINI:
        return _complete_gemini(payload)
    raise LlmProviderError(f"Unsupported LLM provider: {payload.provider}")


def test_llm_key(*, provider: LlmProvider, api_key: str, model: str) -> str:
    return complete_text(
        LlmCompletionRequest(
            provider=provider,
            api_key=api_key,
            model=model,
            system_prompt="You are a concise health-check responder.",
            user_prompt="Reply with exactly: ok",
            max_tokens=8,
            temperature=0,
        )
    )


def _complete_openai_compatible(payload: LlmCompletionRequest) -> str:
    base_url = {
        LlmProvider.OPENAI: "https://api.openai.com/v1",
        LlmProvider.GROQ: "https://api.groq.com/openai/v1",
        LlmProvider.OPENROUTER: "https://openrouter.ai/api/v1",
    }[payload.provider]
    data = {
        "model": payload.model,
        "messages": [
            {"role": "system", "content": payload.system_prompt},
            {"role": "user", "content": payload.user_prompt},
        ],
        "temperature": payload.temperature,
        "max_tokens": payload.max_tokens,
    }
    headers = {"Authorization": f"Bearer {payload.api_key}", "Content-Type": "application/json"}
    if payload.provider == LlmProvider.OPENROUTER:
        headers.update({"HTTP-Referer": "https://jobpilot.local", "X-Title": "JobPilot"})
    body = _post_json(f"{base_url}/chat/completions", data, headers)
    try:
        return str(body["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmProviderError("LLM provider returned an unexpected response") from exc


def _complete_anthropic(payload: LlmCompletionRequest) -> str:
    data = {
        "model": payload.model,
        "system": payload.system_prompt,
        "messages": [{"role": "user", "content": payload.user_prompt}],
        "max_tokens": payload.max_tokens,
        "temperature": payload.temperature,
    }
    body = _post_json(
        "https://api.anthropic.com/v1/messages",
        data,
        {
            "x-api-key": payload.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
    )
    try:
        return str(body["content"][0]["text"])
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmProviderError("Anthropic returned an unexpected response") from exc


def _complete_gemini(payload: LlmCompletionRequest) -> str:
    data = {
        "systemInstruction": {"parts": [{"text": payload.system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": payload.user_prompt}]}],
        "generationConfig": {"temperature": payload.temperature, "maxOutputTokens": payload.max_tokens},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{payload.model}:generateContent?key={payload.api_key}"
    body = _post_json(url, data, {"Content-Type": "application/json"})
    try:
        return str(body["candidates"][0]["content"]["parts"][0]["text"])
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmProviderError("Gemini returned an unexpected response") from exc


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    request = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urlopen(request, timeout=get_settings().llm_request_timeout_seconds) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise LlmProviderError(f"Provider HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise LlmProviderError(str(exc)) from exc
