"""Ashby public job-board connector."""

from __future__ import annotations

from app.providers.http import fetch_json
from app.providers.normalization import clean_html, details_status, parse_datetime, utc_now
from app.schemas.job import JobCreate


def fetch_ashby_jobs(
    board_name: str,
    *,
    company_name: str | None = None,
    max_jobs: int = 500,
) -> list[JobCreate]:
    payload = fetch_json(
        f"https://api.ashbyhq.com/posting-api/job-board/{board_name}?includeCompensation=true"
    )
    items = payload.get("jobs", []) if isinstance(payload, dict) else []
    results: list[JobCreate] = []

    for item in items[:max_jobs]:
        if not isinstance(item, dict) or not item.get("id") or not item.get("title"):
            continue
        description = clean_html(item.get("descriptionHtml"))
        location = item.get("location")
        workplace_type = item.get("workplaceType")
        remote = bool(item.get("isRemote")) or str(workplace_type or "").lower() == "remote"
        job_url = item.get("jobUrl")
        apply_url = item.get("applyUrl") or job_url
        results.append(
            JobCreate(
                source="ashby",
                external_id=f"{board_name}:{item['id']}",
                title=str(item["title"]),
                company=company_name or board_name,
                location=str(location) if location else None,
                description=description,
                apply_url=apply_url,
                source_url=job_url,
                remote=remote,
                employment_type=item.get("employmentType"),
                application_method="external",
                details_status=details_status(description),
                details_fetched_at=utc_now(),
                posted_at=parse_datetime(item.get("publishedAt")),
            )
        )
    return results
