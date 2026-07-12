"""LinkedIn public guest job search connector.

This is a best-effort discovery connector. It uses LinkedIn's public guest job
search surface and normalizes visible job cards into our internal job schema.
"""

from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, timedelta
from html import unescape
from html.parser import HTMLParser
from threading import Lock
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from app.providers.http import ConnectorFetchError, fetch_text
from app.schemas.job import JobCreate


LINKEDIN_GUEST_JOBS_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
LINKEDIN_GUEST_JOB_DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
LINKEDIN_PAGE_SIZE = 10
LINKEDIN_MAX_SEARCH_RESULTS = 1000
LINKEDIN_EMPTY_PAGE_LIMIT = 2
LINKEDIN_DETAIL_MIN_INTERVAL_SECONDS = 0.75
LINKEDIN_DETAIL_MAX_ATTEMPTS = 3
LINKEDIN_MIN_DESCRIPTION_LENGTH = 120

DATE_POSTED_FILTERS = {
    "any": None,
    "past_24h": "r86400",
    "past_week": "r604800",
    "past_month": "r2592000",
}


def fetch_linkedin_jobs(
    *,
    query: str,
    location: str | None = None,
    limit: int = 25,
    offset: int = 0,
    date_posted: str | None = "past_24h",
) -> list[JobCreate]:
    results: list[JobCreate] = []
    seen_ids: set[str] = set()
    start = offset
    pages_fetched = 0
    consecutive_pages_without_new_jobs = 0

    while len(results) < limit and pages_fetched * LINKEDIN_PAGE_SIZE < LINKEDIN_MAX_SEARCH_RESULTS:
        try:
            html = fetch_text(
                _build_search_url(
                    query=query,
                    location=location,
                    start=start,
                    date_posted=date_posted,
                ),
                headers=_linkedin_headers(),
            )
        except ConnectorFetchError:
            if results:
                break
            raise
        pages_fetched += 1
        cards = _parse_job_cards(html)
        if not cards:
            break

        page_added = 0
        for card in cards:
            job = _card_to_job(card)
            if job is None or job.external_id in seen_ids or not _matches_date_filter(job.posted_at, date_posted):
                continue

            seen_ids.add(job.external_id)
            results.append(job)
            page_added += 1
            if len(results) >= limit:
                break

        if page_added == 0:
            consecutive_pages_without_new_jobs += 1
        else:
            consecutive_pages_without_new_jobs = 0

        if consecutive_pages_without_new_jobs >= LINKEDIN_EMPTY_PAGE_LIMIT:
            break

        if len(cards) < LINKEDIN_PAGE_SIZE:
            break

        start += LINKEDIN_PAGE_SIZE

    return results


def enrich_linkedin_jobs(
    jobs: list[JobCreate],
    *,
    max_workers: int = 2,
    min_interval: float = LINKEDIN_DETAIL_MIN_INTERVAL_SECONDS,
    max_attempts: int = LINKEDIN_DETAIL_MAX_ATTEMPTS,
) -> tuple[list[JobCreate], int, int]:
    if not jobs:
        return [], 0, 0

    enriched_by_id: dict[str, JobCreate] = {}
    pacer = _RequestPacer(min_interval)
    with ThreadPoolExecutor(max_workers=min(max_workers, len(jobs))) as executor:
        futures = {
            executor.submit(_enrich_linkedin_job_with_retries, job, pacer, max_attempts): job
            for job in jobs
        }
        for future in as_completed(futures):
            original = futures[future]
            try:
                enriched_by_id[original.external_id] = future.result()
            except Exception as exc:
                enriched_by_id[original.external_id] = original.model_copy(
                    update={
                        "details_status": "failed",
                        "details_error": str(exc)[:1000],
                    }
                )

    enriched = [enriched_by_id[job.external_id] for job in jobs]
    enriched_count = sum(job.details_status == "complete" for job in enriched)
    failed_count = sum(job.details_status == "failed" for job in enriched)
    return enriched, enriched_count, failed_count


def _enrich_linkedin_job_with_retries(
    job: JobCreate,
    pacer: "_RequestPacer",
    max_attempts: int,
) -> JobCreate:
    last_error: ConnectorFetchError | None = None
    for attempt in range(max_attempts):
        pacer.wait()
        try:
            return fetch_linkedin_job_details(job)
        except ConnectorFetchError as exc:
            last_error = exc
            if attempt + 1 >= max_attempts or (exc.status_code is not None and exc.status_code < 500 and exc.status_code != 429):
                raise
            time.sleep(exc.retry_after or min(2 ** attempt, 8))

    raise last_error or ConnectorFetchError("LinkedIn detail enrichment failed")


def fetch_linkedin_job_details(job: JobCreate) -> JobCreate:
    html = fetch_text(
        LINKEDIN_GUEST_JOB_DETAIL_URL.format(job_id=job.external_id),
        headers=_linkedin_headers(),
    )
    detail = _parse_job_detail(html)
    if not _valid_description(detail.get("description")) and job.source_url:
        html = fetch_text(str(job.source_url), headers=_linkedin_headers())
        detail = _parse_job_detail(html)

    if not _valid_description(detail.get("description")):
        raise ConnectorFetchError("LinkedIn returned no complete job description")

    return JobCreate.model_validate(
        {
            **job.model_dump(),
            "description": detail.get("description") or job.description,
            "employment_type": detail.get("employment_type") or job.employment_type,
            "seniority_level": detail.get("seniority_level") or job.seniority_level,
            "application_method": detail.get("application_method") or job.application_method,
            "apply_url": detail.get("apply_url") or job.apply_url,
            "company_url": detail.get("company_url") or job.company_url,
            "details_status": "complete",
            "details_error": None,
            "details_fetched_at": datetime.now(UTC),
        }
    )


def _build_search_url(*, query: str, location: str | None, start: int, date_posted: str | None) -> str:
    params: dict[str, str | int] = {
        "keywords": query,
        "start": start,
        "sortBy": "DD",
    }
    if location:
        params["location"] = location

    date_filter = DATE_POSTED_FILTERS.get(date_posted or "any")
    if date_filter:
        params["f_TPR"] = date_filter

    return f"{LINKEDIN_GUEST_JOBS_URL}?{urlencode(params)}"


def _linkedin_headers() -> dict[str, str]:
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.linkedin.com/jobs/search/",
    }


def _parse_job_cards(html: str) -> list[dict[str, str | None]]:
    cards = _parse_job_cards_with_patterns(html)
    if cards:
        return cards

    parser = _LinkedInJobCardParser()
    parser.feed(html)
    return parser.cards


def _parse_job_cards_with_patterns(html: str) -> list[dict[str, str | None]]:
    cards: list[dict[str, str | None]] = []
    for chunk in re.findall(r"<li\b[^>]*>(.*?)</li>", html, flags=re.IGNORECASE | re.DOTALL):
        title = _extract_class_text(chunk, "base-search-card__title")
        company = _extract_class_text(chunk, "base-search-card__subtitle")
        location = _extract_class_text(chunk, "job-search-card__location")
        url = _extract_attr(chunk, "href", contains="/jobs/view/")
        entity_urn = _extract_attr(chunk, "data-entity-urn")
        posted_at = _extract_attr(chunk, "datetime")

        if not title or not company:
            continue

        cards.append(
            {
                "title": title,
                "company": company,
                "location": location,
                "url": url,
                "posted_at": posted_at,
                "entity_id": entity_urn.rsplit(":", 1)[-1] if entity_urn else None,
            }
        )

    return cards


def _parse_job_detail(html: str) -> dict[str, str | None]:
    description_html = _extract_class_html(html, "show-more-less-html__markup")
    criteria = _extract_job_criteria(html)
    return {
        "description": _html_to_text(description_html) if description_html else None,
        "employment_type": criteria.get("employment type"),
        "seniority_level": criteria.get("seniority level"),
        "application_method": _application_method(html),
        "apply_url": _external_apply_url(html),
        "company_url": _company_url(html),
    }


def _valid_description(value: str | None) -> bool:
    return bool(value and len(value.strip()) >= LINKEDIN_MIN_DESCRIPTION_LENGTH)


def _extract_class_html(html: str, class_name: str) -> str | None:
    pattern = (
        rf'<(?P<tag>[a-z0-9]+)\b[^>]*class="[^"]*\b{re.escape(class_name)}\b[^"]*"[^>]*>'
        rf"(.*?)</(?P=tag)>"
    )
    match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
    return match.group(2) if match else None


def _extract_job_criteria(html: str) -> dict[str, str]:
    criteria: dict[str, str] = {}
    chunks = re.findall(
        r'<li\b[^>]*class="[^"]*description__job-criteria-item[^"]*"[^>]*>(.*?)</li>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for chunk in chunks:
        label = _extract_class_text(chunk, "description__job-criteria-subheader")
        value = _extract_class_text(chunk, "description__job-criteria-text--criteria")
        if label and value:
            criteria[label.lower()] = value
    return criteria


def _application_method(html: str) -> str | None:
    lowered = html.lower()
    if "apply-button__easy-apply-icon-svg" in lowered or "apply-link-onsite" in lowered:
        return "easy_apply"
    if "apply-button__offsite-apply-icon-svg" in lowered or "apply-link-offsite" in lowered:
        return "external"
    return None


def _external_apply_url(html: str) -> str | None:
    for opening_tag in re.findall(r"<a\b[^>]*>", html, flags=re.IGNORECASE):
        if "apply" not in opening_tag.lower():
            continue
        href = _extract_attr(opening_tag, "href")
        if not href:
            continue
        parsed = urlparse(href)
        if parsed.scheme in {"http", "https"} and "linkedin.com" not in parsed.netloc.lower():
            return href
    return None


def _company_url(html: str) -> str | None:
    for opening_tag in re.findall(r"<a\b[^>]*>", html, flags=re.IGNORECASE):
        if "topcard__org-name" not in opening_tag.lower():
            continue
        href = _extract_attr(opening_tag, "href")
        if href:
            return _canonical_url(href)
    return None


def _html_to_text(value: str) -> str | None:
    parser = _ReadableHTMLParser()
    parser.feed(value)
    return parser.text()


def _extract_class_text(html: str, class_name: str) -> str | None:
    pattern = rf'<[^>]*class="[^"]*\b{re.escape(class_name)}\b[^"]*"[^>]*>(.*?)</[^>]+>'
    match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return _strip_tags(match.group(1))


def _extract_attr(html: str, attr_name: str, *, contains: str | None = None) -> str | None:
    pattern = rf'{re.escape(attr_name)}="([^"]+)"'
    for match in re.finditer(pattern, html, flags=re.IGNORECASE):
        value = unescape(match.group(1))
        if contains is None or contains in value:
            return value
    return None


def _strip_tags(value: str) -> str | None:
    text = re.sub(r"<[^>]+>", " ", value)
    return _clean_text(text)


def _card_to_job(card: dict[str, str | None]) -> JobCreate | None:
    title = _clean_text(card.get("title"))
    company = _clean_text(card.get("company"))
    url = _canonical_job_url(card.get("url"))

    if not title or not company or not url:
        return None

    external_id = _external_id_from_url(url) or card.get("entity_id") or url
    location = _clean_text(card.get("location"))

    return JobCreate(
        source="linkedin",
        external_id=str(external_id),
        title=title,
        company=company,
        location=location,
        description=None,
        apply_url=url,
        source_url=url,
        remote=bool(location and "remote" in location.lower()),
        employment_type=None,
        posted_at=_parse_date(card.get("posted_at")),
    )


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    text = " ".join(unescape(value).split())
    return text or None


def _canonical_job_url(value: str | None) -> str | None:
    if not value:
        return None

    parsed = urlparse(unescape(value))
    if not parsed.scheme or not parsed.netloc:
        return None

    query = parse_qs(parsed.query)
    keep_query = {}
    if "currentJobId" in query:
        keep_query["currentJobId"] = query["currentJobId"][0]

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            "",
            urlencode(keep_query),
            "",
        )
    )


def _canonical_url(value: str) -> str:
    parsed = urlparse(unescape(value))
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))


def _external_id_from_url(value: str) -> str | None:
    parsed = urlparse(value)
    path_parts = [part for part in parsed.path.split("/") if part]
    for part in reversed(path_parts):
        if part.isdigit():
            return part

    query = parse_qs(parsed.query)
    current_job_id = query.get("currentJobId", [None])[0]
    return current_job_id if current_job_id and current_job_id.isdigit() else None


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.combine(date.fromisoformat(value), datetime.min.time())
    except ValueError:
        return None


def _matches_date_filter(posted_at: datetime | None, date_posted: str | None) -> bool:
    if posted_at is None or not date_posted or date_posted == "any":
        return True

    days = {"past_24h": 1, "past_week": 7, "past_month": 30}.get(date_posted)
    if days is None:
        return True
    return posted_at.date() >= (datetime.now(UTC).date() - timedelta(days=days))


class _ReadableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "li":
            self._parts.append("\n- ")
        elif tag in {"br", "p", "div", "h1", "h2", "h3", "h4"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"li", "p", "div", "h1", "h2", "h3", "h4"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def text(self) -> str | None:
        lines = [" ".join(line.split()) for line in "".join(self._parts).splitlines()]
        text = "\n".join(line for line in lines if line)
        return unescape(text) or None


class _RequestPacer:
    def __init__(self, min_interval: float) -> None:
        self._min_interval = max(0.0, min_interval)
        self._next_request_at = 0.0
        self._lock = Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delay = max(0.0, self._next_request_at - now)
            self._next_request_at = max(now, self._next_request_at) + self._min_interval
        if delay:
            time.sleep(delay)


class _LinkedInJobCardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cards: list[dict[str, str | None]] = []
        self._current: dict[str, str | None] | None = None
        self._capture_field: str | None = None
        self._capture_parts: list[str] = []
        self._card_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        class_names = attr.get("class") or ""

        if self._current is None and tag == "li":
            self._current = {
                "title": None,
                "company": None,
                "location": None,
                "url": None,
                "posted_at": None,
                "entity_id": None,
            }
            self._card_depth = 1
            return

        if self._current is None:
            return

        self._card_depth += 1

        entity_urn = attr.get("data-entity-urn")
        if entity_urn and not self._current.get("entity_id"):
            self._current["entity_id"] = entity_urn.rsplit(":", 1)[-1]

        if tag == "a" and not self._current.get("url"):
            href = attr.get("href")
            if href and "/jobs/view/" in href:
                self._current["url"] = href

        if tag == "time" and attr.get("datetime"):
            self._current["posted_at"] = attr.get("datetime")

        field = _field_for_class(class_names)
        if field:
            self._capture_field = field
            self._capture_parts = []

    def handle_data(self, data: str) -> None:
        if self._capture_field:
            self._capture_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._current is None:
            return

        if self._capture_field and self._capture_parts:
            self._current[self._capture_field] = " ".join(self._capture_parts)
            self._capture_field = None
            self._capture_parts = []

        self._card_depth -= 1
        if tag == "li" and self._card_depth <= 0:
            if self._current.get("title") and self._current.get("company"):
                self.cards.append(self._current)
            self._current = None
            self._capture_field = None
            self._capture_parts = []
            self._card_depth = 0


def _field_for_class(class_names: str) -> str | None:
    class_set = set(class_names.split())
    if "base-search-card__title" in class_set:
        return "title"
    if "base-search-card__subtitle" in class_set:
        return "company"
    if "job-search-card__location" in class_set:
        return "location"
    return None
