"""Detect public ATS career-site families from stable URL signatures."""

from __future__ import annotations

from dataclasses import dataclass
import re
from html import unescape
from urllib.parse import parse_qs, urlparse

from app.providers.generic_career import require_public_url
from app.providers.http import fetch_text


@dataclass(frozen=True)
class DetectedATS:
    ats_type: str
    identifier: str | None
    confidence: str


def detect_ats(careers_url: str | None) -> DetectedATS:
    if not careers_url:
        return DetectedATS("unknown", None, "none")

    parsed = urlparse(careers_url)
    host = (parsed.hostname or "").lower()
    parts = [part for part in parsed.path.split("/") if part]
    query = parse_qs(parsed.query)

    if "greenhouse.io" in host:
        identifier = parts[0] if parts else None
        return DetectedATS("greenhouse", identifier, "high")

    if host in {"jobs.lever.co", "api.lever.co"} or host.endswith(".jobs.lever.co"):
        return DetectedATS("lever", parts[0] if parts else None, "high")

    if host in {"jobs.ashbyhq.com", "api.ashbyhq.com"}:
        board = parts[-1] if host == "api.ashbyhq.com" and parts else (parts[0] if parts else None)
        return DetectedATS("ashby", board, "high")

    if host in {"careers.smartrecruiters.com", "jobs.smartrecruiters.com"}:
        return DetectedATS("smartrecruiters", parts[0] if parts else None, "high")

    if host == "api.smartrecruiters.com":
        try:
            company_index = parts.index("companies") + 1
            identifier = parts[company_index]
        except (ValueError, IndexError):
            identifier = None
        return DetectedATS("smartrecruiters", identifier, "high")

    if host.endswith("myworkdayjobs.com") or ".myworkdayjobs.com" in host:
        site = parts[0] if parts else None
        tenant = host.split(".", 1)[0]
        identifier = f"{tenant}|{site}" if site else tenant
        return DetectedATS("workday", identifier, "high")

    if "icims.com" in host:
        return DetectedATS("icims", host, "high")

    if "oraclecloud.com" in host or "taleo.net" in host:
        return DetectedATS("oracle", host, "high")

    if "successfactors" in host or "jobs2web.com" in host:
        return DetectedATS("successfactors", host, "high")

    if "avature.net" in host:
        return DetectedATS("avature", host, "high")

    if "phenompeople.com" in host:
        return DetectedATS("phenom", host, "high")

    if query.get("gh_jid"):
        return DetectedATS("greenhouse", None, "medium")

    return DetectedATS("generic", host or None, "low")


def probe_ats(careers_url: str) -> DetectedATS:
    direct = detect_ats(careers_url)
    if direct.ats_type not in {"generic", "unknown"}:
        return direct

    require_public_url(careers_url)
    html = fetch_text(careers_url)
    normalized = unescape(html).replace("\\/", "/")
    candidates = re.findall(r"https?://[^\"'<>\s]+", normalized, flags=re.IGNORECASE)
    for candidate in candidates:
        detected = detect_ats(candidate.rstrip(")],;"))
        if detected.ats_type not in {"generic", "unknown"} and detected.identifier:
            return DetectedATS(detected.ats_type, detected.identifier, "medium")

    signatures = (
        (r"boards-api\.greenhouse\.io/v1/boards/([a-zA-Z0-9_-]+)", "greenhouse"),
        (r"api\.lever\.co/v0/postings/([a-zA-Z0-9_-]+)", "lever"),
        (r"api\.ashbyhq\.com/posting-api/job-board/([a-zA-Z0-9_-]+)", "ashby"),
    )
    for pattern, ats_type in signatures:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            return DetectedATS(ats_type, match.group(1), "medium")
    return direct
