"""SmartRecruiters public Posting API connector."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from app.providers.http import ConnectorFetchError, fetch_json
from app.providers.normalization import clean_html, details_status, parse_datetime, utc_now
from app.schemas.job import JobCreate


SMARTRECRUITERS_API = "https://api.smartrecruiters.com/v1/companies"


def fetch_smartrecruiters_jobs(
    company_identifier: str,
    *,
    company_name: str | None = None,
    max_jobs: int = 100,
    max_workers: int = 8,
) -> list[JobCreate]:
    summaries: list[dict] = []
    offset = 0
    while len(summaries) < max_jobs:
        limit = min(100, max_jobs - len(summaries))
        payload = fetch_json(
            f"{SMARTRECRUITERS_API}/{company_identifier}/postings?limit={limit}&offset={offset}"
        )
        page = payload.get("content", []) if isinstance(payload, dict) else []
        summaries.extend(item for item in page if isinstance(item, dict))
        if not page or len(page) < limit:
            break
        offset += len(page)

    results_by_id: dict[str, JobCreate] = {}
    with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(summaries)))) as executor:
        futures = {
            executor.submit(_fetch_detail, company_identifier, item, company_name): item
            for item in summaries[:max_jobs]
        }
        for future in as_completed(futures):
            summary = futures[future]
            try:
                job = future.result()
            except ConnectorFetchError:
                job = _to_job(company_identifier, summary, summary, company_name)
            if job is not None:
                results_by_id[job.external_id] = job

    return list(results_by_id.values())


def _fetch_detail(company_identifier: str, summary: dict, company_name: str | None) -> JobCreate | None:
    posting_id = summary.get("id")
    if not posting_id:
        return None
    detail = fetch_json(f"{SMARTRECRUITERS_API}/{company_identifier}/postings/{posting_id}")
    return _to_job(company_identifier, summary, detail if isinstance(detail, dict) else {}, company_name)


def _to_job(
    company_identifier: str,
    summary: dict,
    detail: dict,
    company_name: str | None,
) -> JobCreate | None:
    posting_id = detail.get("id") or summary.get("id")
    title = detail.get("name") or summary.get("name")
    if not posting_id or not title:
        return None

    location_data = detail.get("location") or summary.get("location") or {}
    location = location_data.get("fullLocation") if isinstance(location_data, dict) else None
    sections = ((detail.get("jobAd") or {}).get("sections") or {}) if isinstance(detail, dict) else {}
    description_parts: list[str] = []
    for key in ("companyDescription", "jobDescription", "qualifications", "additionalInformation"):
        section = sections.get(key) or {}
        text = clean_html(section.get("text")) if isinstance(section, dict) else None
        if text:
            heading = section.get("title")
            description_parts.append(f"{heading}\n{text}" if heading else text)
    description = "\n\n".join(description_parts) or None
    posting_url = detail.get("postingUrl") or summary.get("ref")
    apply_url = detail.get("applyUrl") or posting_url
    employment = detail.get("typeOfEmployment") or summary.get("typeOfEmployment") or {}
    experience = detail.get("experienceLevel") or summary.get("experienceLevel") or {}
    resolved_company = detail.get("company") or summary.get("company") or {}

    return JobCreate(
        source="smartrecruiters",
        external_id=f"{company_identifier}:{posting_id}",
        title=str(title),
        company=company_name or resolved_company.get("name") or company_identifier,
        location=location,
        description=description,
        apply_url=apply_url,
        source_url=posting_url,
        remote=bool(isinstance(location_data, dict) and location_data.get("remote")),
        employment_type=employment.get("label") if isinstance(employment, dict) else None,
        seniority_level=experience.get("label") if isinstance(experience, dict) else None,
        application_method="external",
        details_status=details_status(description),
        details_fetched_at=utc_now(),
        posted_at=parse_datetime(detail.get("releasedDate") or summary.get("releasedDate")),
    )
