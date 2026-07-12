"""Production-oriented web search providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import urlparse

from app.core.config import get_settings
from app.providers.http import get_json, post_json
from app.providers.sources import JobSource
from app.providers.web_search import SearchResult, discover_job_links


@dataclass(frozen=True)
class SearchProviderResult:
    provider: str
    items: list[SearchResult]


class WebSearchProvider(ABC):
    name: str

    @abstractmethod
    def search(self, *, source: JobSource, query: str, location: str | None, limit: int) -> list[SearchResult]:
        raise NotImplementedError


class FirecrawlSearchProvider(WebSearchProvider):
    name = "firecrawl"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def search(self, *, source: JobSource, query: str, location: str | None, limit: int) -> list[SearchResult]:
        payload = {
            "query": build_source_query(source, query, location),
            "limit": limit,
        }
        response = post_json(
            "https://api.firecrawl.dev/v2/search",
            payload=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        data = response.get("data", []) if isinstance(response, dict) else []
        return filter_results(source, [_result_from_mapping(item) for item in data])[:limit]


class BraveSearchProvider(WebSearchProvider):
    name = "brave"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def search(self, *, source: JobSource, query: str, location: str | None, limit: int) -> list[SearchResult]:
        response = get_json(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": build_source_query(source, query, location), "count": limit},
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key,
            },
        )
        web = response.get("web", {}) if isinstance(response, dict) else {}
        data = web.get("results", []) if isinstance(web, dict) else []
        return filter_results(source, [_result_from_mapping(item) for item in data])[:limit]


class HtmlFallbackSearchProvider(WebSearchProvider):
    name = "html_fallback"

    def search(self, *, source: JobSource, query: str, location: str | None, limit: int) -> list[SearchResult]:
        return discover_job_links(source, query, location, limit)


def search_web(source: JobSource, query: str, location: str | None, limit: int) -> SearchProviderResult:
    provider = get_search_provider()
    items = provider.search(source=source, query=query, location=location, limit=limit)
    return SearchProviderResult(provider=provider.name, items=items)


def get_search_provider() -> WebSearchProvider:
    settings = get_settings()
    provider = settings.web_search_provider.lower()

    if provider in {"auto", "firecrawl"} and settings.firecrawl_api_key:
        return FirecrawlSearchProvider(settings.firecrawl_api_key)

    if provider in {"auto", "brave"} and settings.brave_search_api_key:
        return BraveSearchProvider(settings.brave_search_api_key)

    return HtmlFallbackSearchProvider()


def build_source_query(source: JobSource, query: str, location: str | None) -> str:
    location_part = f" {location}" if location else ""

    if source == JobSource.LINKEDIN:
        return f'site:linkedin.com/jobs "{query}"{location_part}'
    if source == JobSource.INDEED:
        return f'site:indeed.com "{query}"{location_part}'
    if source == JobSource.CAREER_PAGES:
        return f'("{query}"{location_part}) ("careers" OR "jobs" OR "apply")'

    return f'"{query}"{location_part} jobs apply'


def filter_results(source: JobSource, results: list[SearchResult]) -> list[SearchResult]:
    filtered: list[SearchResult] = []
    for result in results:
        parsed = urlparse(result.url)
        host = parsed.netloc.lower()
        path = parsed.path.lower()
        url = result.url.lower()

        if source == JobSource.LINKEDIN and "linkedin.com" in host and "/jobs" in path:
            filtered.append(result)
        elif source == JobSource.INDEED and "indeed." in host and ("viewjob" in url or "/jobs" in path):
            filtered.append(result)
        elif source == JobSource.CAREER_PAGES and _looks_like_career_page(host, path, url):
            filtered.append(result)

    return _dedupe_results(filtered)


def _result_from_mapping(item: dict) -> SearchResult:
    title = str(item.get("title") or item.get("name") or "Untitled")
    url = str(item.get("url") or item.get("link") or "")
    return SearchResult(title=title, url=url)


def _looks_like_career_page(host: str, path: str, url: str) -> bool:
    career_markers = [
        "careers",
        "jobs",
        "greenhouse.io",
        "lever.co",
        "ashbyhq.com",
        "myworkdayjobs.com",
        "smartrecruiters.com",
    ]
    return any(marker in host or marker in path or marker in url for marker in career_markers)


def _dedupe_results(results: list[SearchResult]) -> list[SearchResult]:
    seen: set[str] = set()
    unique: list[SearchResult] = []
    for result in results:
        if not result.url or result.url in seen:
            continue
        seen.add(result.url)
        unique.append(result)
    return unique
