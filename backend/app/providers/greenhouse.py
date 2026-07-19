"""Greenhouse public job board connector."""

from __future__ import annotations

from app.providers.http import fetch_json
from app.providers.normalization import clean_html, details_status, parse_datetime, utc_now
from app.schemas.job import JobCreate


def fetch_greenhouse_jobs(
    board_token: str,
    *,
    company_name: str | None = None,
    max_jobs: int = 1000,
) -> list[JobCreate]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
    payload = fetch_json(url)
    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
    results: list[JobCreate] = []

    for item in jobs[:max_jobs]:
        if not isinstance(item, dict):
            continue

        location = item.get("location") or {}
        location_name = location.get("name") if isinstance(location, dict) else None
        absolute_url = item.get("absolute_url")
        title = item.get("title")
        external_id = item.get("id")

        if not title or external_id is None:
            continue

        description = clean_html(item.get("content"))
        results.append(
            JobCreate(
                source="greenhouse",
                external_id=f"{board_token}:{external_id}",
                title=title,
                company=company_name or item.get("company_name") or board_token,
                location=location_name,
                description=description,
                apply_url=absolute_url,
                source_url=absolute_url,
                remote=bool(location_name and "remote" in location_name.lower()),
                employment_type=None,
                application_method="external",
                details_status=details_status(description),
                details_fetched_at=utc_now(),
                posted_at=parse_datetime(item.get("first_published") or item.get("updated_at")),
            )
        )

    return results
