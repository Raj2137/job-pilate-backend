"""Bounded fallback for career pages exposing schema.org JobPosting data."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from app.providers.http import ConnectorFetchError, fetch_text
from app.providers.normalization import clean_html, details_status, parse_datetime, utc_now
from app.schemas.job import JobCreate


class _CareerPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.json_ld: list[str] = []
        self.links: list[str] = []
        self._in_json_ld = False
        self._script_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "script" and "ld+json" in (attributes.get("type") or "").lower():
            self._in_json_ld = True
            self._script_parts = []
        elif tag == "a" and attributes.get("href"):
            self.links.append(attributes["href"] or "")

    def handle_data(self, data: str) -> None:
        if self._in_json_ld:
            self._script_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_json_ld:
            self.json_ld.append("".join(self._script_parts))
            self._in_json_ld = False
            self._script_parts = []


def fetch_generic_career_jobs(
    careers_url: str,
    *,
    company_name: str,
    max_jobs: int = 50,
    max_detail_pages: int = 30,
) -> list[JobCreate]:
    require_public_url(careers_url)
    html = fetch_text(careers_url)
    jobs = _jobs_from_html(html, base_url=careers_url, company_name=company_name)
    if len(jobs) >= max_jobs:
        return jobs[:max_jobs]

    parser = _CareerPageParser()
    parser.feed(html)
    detail_urls = _candidate_job_links(parser.links, base_url=careers_url)
    seen_ids = {job.external_id for job in jobs}
    for detail_url in detail_urls[:max_detail_pages]:
        if len(jobs) >= max_jobs:
            break
        try:
            detail_html = fetch_text(detail_url)
        except ConnectorFetchError:
            continue
        for job in _jobs_from_html(detail_html, base_url=detail_url, company_name=company_name):
            if job.external_id not in seen_ids:
                seen_ids.add(job.external_id)
                jobs.append(job)
    return jobs[:max_jobs]


def _jobs_from_html(html: str, *, base_url: str, company_name: str) -> list[JobCreate]:
    parser = _CareerPageParser()
    parser.feed(html)
    nodes: list[dict] = []
    for raw in parser.json_ld:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        nodes.extend(_find_job_postings(payload))

    jobs: list[JobCreate] = []
    for node in nodes:
        job = _job_from_schema(node, base_url=base_url, fallback_company=company_name)
        if job is not None:
            jobs.append(job)
    return jobs


def _find_job_postings(value) -> list[dict]:
    results: list[dict] = []
    if isinstance(value, dict):
        node_type = value.get("@type")
        types = node_type if isinstance(node_type, list) else [node_type]
        if "JobPosting" in types:
            results.append(value)
        for child in value.values():
            results.extend(_find_job_postings(child))
    elif isinstance(value, list):
        for child in value:
            results.extend(_find_job_postings(child))
    return results


def _job_from_schema(node: dict, *, base_url: str, fallback_company: str) -> JobCreate | None:
    title = node.get("title")
    if not title:
        return None
    source_url = urljoin(base_url, node.get("url") or base_url)
    if not _same_public_site(source_url, base_url):
        source_url = base_url
    organization = node.get("hiringOrganization") or {}
    company = organization.get("name") if isinstance(organization, dict) else None
    description = clean_html(node.get("description"))
    location = _schema_location(node.get("jobLocation"))
    remote = str(node.get("jobLocationType") or "").upper() == "TELECOMMUTE" or bool(
        location and "remote" in location.lower()
    )
    identifier = node.get("identifier")
    if isinstance(identifier, dict):
        identifier = identifier.get("value") or identifier.get("name")
    external_id = str(identifier or hashlib.sha256(source_url.encode("utf-8")).hexdigest())
    employment = node.get("employmentType")
    if isinstance(employment, list):
        employment = ", ".join(str(item) for item in employment)
    return JobCreate(
        source="career_page",
        external_id=external_id,
        title=str(title),
        company=str(company or fallback_company),
        location=location,
        description=description,
        apply_url=source_url,
        source_url=source_url,
        remote=remote,
        employment_type=str(employment) if employment else None,
        application_method="external",
        details_status=details_status(description),
        details_fetched_at=utc_now(),
        posted_at=parse_datetime(node.get("datePosted")),
    )


def _schema_location(value) -> str | None:
    locations = value if isinstance(value, list) else [value]
    rendered: list[str] = []
    for location in locations:
        if not isinstance(location, dict):
            continue
        address = location.get("address") or {}
        if isinstance(address, str):
            rendered.append(address)
            continue
        parts = [
            address.get("addressLocality"),
            address.get("addressRegion"),
            address.get("addressCountry"),
        ]
        text = ", ".join(str(part) for part in parts if part)
        if text:
            rendered.append(text)
    return "; ".join(dict.fromkeys(rendered)) or None


def _candidate_job_links(links: list[str], *, base_url: str) -> list[str]:
    candidates: list[str] = []
    for href in links:
        absolute = urljoin(base_url, href)
        path = urlparse(absolute).path.lower()
        if not any(token in path for token in ("/job/", "/jobs/", "/career/", "/position/")):
            continue
        if _same_public_site(absolute, base_url) and absolute not in candidates:
            candidates.append(absolute)
    return candidates


def _same_public_site(url: str, base_url: str) -> bool:
    parsed = urlparse(url)
    base = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or not base.hostname:
        return False
    host = parsed.hostname.lower()
    base_host = base.hostname.lower()
    return host == base_host or host.endswith(f".{base_host}") or base_host.endswith(f".{host}")


def require_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ConnectorFetchError("Career URL must be a public HTTP or HTTPS URL")
    host = parsed.hostname.lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ConnectorFetchError("Private career URLs are not allowed")
    try:
        addresses = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ConnectorFetchError(f"Career host could not be resolved: {host}") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ConnectorFetchError("Private career URLs are not allowed")
