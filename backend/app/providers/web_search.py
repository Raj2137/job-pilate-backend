"""Lightweight web search for finding candidate job links."""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from app.providers.http import fetch_text
from app.providers.sources import JobSource


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchResult] = []
        self._inside_link = False
        self._current_href: str | None = None
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            attr_map = dict(attrs)
            self._inside_link = True
            self._current_href = attr_map.get("href")
            self._title_parts = []

    def handle_data(self, data: str) -> None:
        if self._inside_link:
            self._title_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self._inside_link:
            return

        title = " ".join(part.strip() for part in self._title_parts if part.strip())
        url = _normalize_search_url(self._current_href)
        if title and url:
            self.results.append(SearchResult(title=unescape(title), url=url))

        self._inside_link = False
        self._current_href = None
        self._title_parts = []


def discover_job_links(source: JobSource, query: str, location: str | None, limit: int) -> list[SearchResult]:
    from app.providers.web_search_providers import build_source_query, filter_results

    search_query = build_source_query(source, query, location)
    results: list[SearchResult] = []

    for url in _build_search_urls(search_query):
        html = fetch_text(url)
        parser = LinkParser()
        parser.feed(html)
        results.extend(filter_results(source, parser.results))
        results = _dedupe_results(results)
        if len(results) >= limit:
            break

    return results[:limit]


def _build_search_urls(search_query: str) -> list[str]:
    encoded = quote_plus(search_query)
    return [
        f"https://duckduckgo.com/html/?q={encoded}",
        f"https://lite.duckduckgo.com/lite/?q={encoded}",
        f"https://www.bing.com/search?q={encoded}",
    ]


def _normalize_search_url(url: str | None) -> str | None:
    if not url:
        return None

    parsed = urlparse(unescape(url))
    if parsed.path.startswith("/l/"):
        uddg = parse_qs(parsed.query).get("uddg")
        if uddg:
            return unquote(uddg[0])

    if parsed.netloc.endswith("bing.com") and parsed.path == "/ck/a":
        target = parse_qs(parsed.query).get("u")
        if target:
            return unquote(target[0])

    if parsed.scheme in {"http", "https"} and not _is_search_engine_internal_url(parsed.netloc):
        return unescape(url)

    return None


def _is_search_engine_internal_url(host: str) -> bool:
    blocked_hosts = [
        "duckduckgo.com",
        "lite.duckduckgo.com",
        "bing.com",
        "www.bing.com",
        "microsoft.com",
    ]
    return any(host == blocked or host.endswith(f".{blocked}") for blocked in blocked_hosts)


def _dedupe_results(results: list[SearchResult]) -> list[SearchResult]:
    seen: set[str] = set()
    unique: list[SearchResult] = []
    for result in results:
        if result.url in seen:
            continue
        seen.add(result.url)
        unique.append(result)
    return unique
