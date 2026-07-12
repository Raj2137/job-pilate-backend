"""Workday public external-career-site connector."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from urllib.parse import urlparse

from app.providers.http import ConnectorFetchError, fetch_json, post_json
from app.providers.normalization import clean_html, details_status, parse_datetime, utc_now
from app.schemas.job import JobCreate


@dataclass(frozen=True)
class WorkdaySite:
    origin: str
    tenant: str
    site: str

    @property
    def api_base(self) -> str:
        return f"{self.origin}/wday/cxs/{self.tenant}/{self.site}"


def parse_workday_site(careers_url: str) -> WorkdaySite:
    parsed = urlparse(careers_url)
    if not parsed.scheme or not parsed.netloc or "myworkdayjobs.com" not in parsed.netloc.lower():
        raise ConnectorFetchError("Invalid Workday external career-site URL")
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        raise ConnectorFetchError("Workday career-site name is missing from URL")
    return WorkdaySite(
        origin=f"{parsed.scheme}://{parsed.netloc}",
        tenant=parsed.netloc.split(".", 1)[0],
        site=parts[0],
    )


def fetch_workday_jobs(
    careers_url: str,
    *,
    company_name: str,
    max_jobs: int = 100,
    max_workers: int = 8,
) -> list[JobCreate]:
    site = parse_workday_site(careers_url)
    summaries: list[dict] = []
    offset = 0
    page_size = 20
    while len(summaries) < max_jobs:
        payload = post_json(
            f"{site.api_base}/jobs",
            payload={
                "appliedFacets": {},
                "limit": min(page_size, max_jobs - len(summaries)),
                "offset": offset,
                "searchText": "",
            },
        )
        page = payload.get("jobPostings", []) if isinstance(payload, dict) else []
        summaries.extend(item for item in page if isinstance(item, dict))
        if not page or len(page) < min(page_size, max_jobs - offset):
            break
        offset += len(page)

    results: list[JobCreate] = []
    with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(summaries)))) as executor:
        futures = {
            executor.submit(_fetch_workday_detail, site, summary, company_name): summary
            for summary in summaries[:max_jobs]
        }
        for future in as_completed(futures):
            try:
                job = future.result()
            except ConnectorFetchError:
                job = None
            if job is not None:
                results.append(job)
    return results


def _fetch_workday_detail(site: WorkdaySite, summary: dict, company_name: str) -> JobCreate | None:
    external_path = summary.get("externalPath")
    if not external_path:
        return None
    payload = fetch_json(f"{site.api_base}{external_path}")
    info = payload.get("jobPostingInfo", {}) if isinstance(payload, dict) else {}
    title = info.get("title") or summary.get("title")
    job_id = info.get("jobReqId") or info.get("id") or external_path
    if not title:
        return None
    description = clean_html(info.get("jobDescription"))
    locations = [info.get("location"), *(info.get("additionalLocations") or [])]
    location = "; ".join(str(item) for item in locations if item) or summary.get("locationsText")
    source_url = f"{site.origin}/{site.site}{external_path}"
    remote = any("remote" in str(item).lower() for item in locations if item)
    return JobCreate(
        source="workday",
        external_id=f"{site.tenant}:{site.site}:{job_id}",
        title=str(title),
        company=company_name,
        location=location,
        description=description,
        apply_url=source_url,
        source_url=source_url,
        remote=remote,
        employment_type=info.get("timeType"),
        application_method="external",
        details_status=details_status(description),
        details_fetched_at=utc_now(),
        posted_at=parse_datetime(info.get("startDate")),
    )
