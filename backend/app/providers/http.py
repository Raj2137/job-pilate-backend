"""Small HTTP helpers for public job connectors."""

from __future__ import annotations

import json
import ssl
from typing import Any
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import certifi
except ImportError:  # pragma: no cover - dependency is listed, fallback keeps local dev forgiving.
    certifi = None


class ConnectorFetchError(Exception):
    """Raised when a connector cannot fetch or parse remote data."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


def browser_headers(*, referer: str | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    if referer:
        headers["Referer"] = referer
    return headers


def fetch_json(url: str, *, headers: dict[str, str] | None = None, timeout: int = 20) -> Any:
    request_headers = {**browser_headers(), **(headers or {})}
    request = Request(url, headers=request_headers)
    context = ssl.create_default_context(cafile=certifi.where() if certifi else None)
    try:
        with urlopen(request, timeout=timeout, context=context) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ConnectorFetchError(str(exc)) from exc


def fetch_text(url: str, *, headers: dict[str, str] | None = None, timeout: int = 20) -> str:
    request_headers = {**browser_headers(referer=url), **(headers or {})}
    request = Request(url, headers=request_headers)
    context = ssl.create_default_context(cafile=certifi.where() if certifi else None)
    try:
        with urlopen(request, timeout=timeout, context=context) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except HTTPError as exc:
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        raise ConnectorFetchError(
            str(exc),
            status_code=exc.code,
            retry_after=float(retry_after) if retry_after and retry_after.isdigit() else None,
        ) from exc
    except (URLError, TimeoutError) as exc:
        raise ConnectorFetchError(str(exc)) from exc


def get_json(url: str, *, params: dict[str, str | int] | None = None, headers: dict[str, str] | None = None, timeout: int = 20) -> Any:
    if params:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urlencode(params)}"
    return fetch_json(url, headers=headers, timeout=timeout)


def post_json(url: str, *, payload: dict[str, Any], headers: dict[str, str] | None = None, timeout: int = 30) -> Any:
    request_headers = {
        **browser_headers(referer=url),
        "Content-Type": "application/json",
        **(headers or {}),
    }
    request = Request(url, data=json.dumps(payload).encode("utf-8"), headers=request_headers, method="POST")
    context = ssl.create_default_context(cafile=certifi.where() if certifi else None)
    try:
        with urlopen(request, timeout=timeout, context=context) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ConnectorFetchError(str(exc)) from exc
