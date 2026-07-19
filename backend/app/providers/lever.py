"""Lever public postings connector."""

from __future__ import annotations

from datetime import UTC, datetime

from app.providers.http import fetch_json
from app.providers.normalization import clean_html, details_status, utc_now
from app.schemas.job import JobCreate


def _clean_html(value: str | None) -> str | None:
    return clean_html(value)


def _build_description(item: dict) -> str | None:
    parts: list[str] = []
    for section in item.get("lists", []) or []:
        if not isinstance(section, dict):
            continue
        heading = section.get("text")
        content = section.get("content")
        if heading:
            parts.append(str(heading))
        if content:
            parts.append(_clean_html(str(content)) or "")
    return "\n\n".join(part for part in parts if part).strip() or None


def fetch_lever_jobs(
    site: str,
    *,
    company_name: str | None = None,
    max_jobs: int = 1000,
) -> list[JobCreate]:
    url = f"https://api.lever.co/v0/postings/{site}?mode=json"
    payload = fetch_json(url)
    jobs = payload if isinstance(payload, list) else []
    results: list[JobCreate] = []

    for item in jobs[:max_jobs]:
        if not isinstance(item, dict):
            continue

        categories = item.get("categories") or {}
        location = categories.get("location") if isinstance(categories, dict) else None
        commitment = categories.get("commitment") if isinstance(categories, dict) else None
        hosted_url = item.get("hostedUrl")
        title = item.get("text")
        external_id = item.get("id")

        if not title or not external_id:
            continue

        description = _build_description(item)
        created_at = item.get("createdAt")
        posted_at = (
            datetime.fromtimestamp(created_at / 1000, tz=UTC).replace(tzinfo=None)
            if isinstance(created_at, (int, float))
            else None
        )
        results.append(
            JobCreate(
                source="lever",
                external_id=f"{site}:{external_id}",
                title=title,
                company=company_name or site,
                location=location,
                description=description,
                apply_url=hosted_url,
                source_url=hosted_url,
                remote=bool(location and "remote" in location.lower()),
                employment_type=commitment,
                application_method="external",
                details_status=details_status(description),
                details_fetched_at=utc_now(),
                posted_at=posted_at,
            )
        )

    return results
