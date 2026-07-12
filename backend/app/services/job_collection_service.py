"""Job collection orchestration."""

from sqlalchemy.orm import Session

from app.providers.ashby import fetch_ashby_jobs
from app.providers.ats_detection import detect_ats, probe_ats
from app.providers.career_pages import DEFAULT_CAREER_PAGE_TARGETS, split_career_page_targets
from app.providers.generic_career import fetch_generic_career_jobs
from app.providers.greenhouse import fetch_greenhouse_jobs
from app.providers.http import ConnectorFetchError
from app.providers.linkedin import enrich_linkedin_jobs, fetch_linkedin_jobs
from app.providers.lever import fetch_lever_jobs
from app.providers.search_urls import build_indeed_jobs_url, build_linkedin_jobs_url
from app.providers.sources import JobSource
from app.providers.smartrecruiters import fetch_smartrecruiters_jobs
from app.providers.workday import fetch_workday_jobs
from app.repositories.company_repository import (
    get_company_by_name,
    record_company_collection_failure,
    record_company_collection_success,
)
from app.repositories.search_segment_repository import utc_now
from app.repositories.job_repository import (
    count_linkedin_jobs_needing_enrichment,
    get_jobs_by_external_ids,
    list_linkedin_jobs_needing_enrichment,
    search_jobs_by_company,
    upsert_job,
    upsert_jobs,
)
from app.schemas.job import (
    CompanyJobCollectionRequest,
    CompanyJobCollectionResult,
    JobCollectionRequest,
    JobCollectionResult,
    JobCreate,
    JobSourceCollectionResult,
    LinkedInEnrichmentRequest,
    LinkedInEnrichmentResult,
)


def collect_jobs(db: Session, payload: JobCollectionRequest) -> JobCollectionResult:
    sources = payload.sources or [JobSource.CAREER_PAGES]
    results: list[JobSourceCollectionResult] = []
    total_saved = 0

    if JobSource.CAREER_PAGES in sources:
        sources = list(dict.fromkeys([*sources, JobSource.GREENHOUSE, JobSource.LEVER]))
        if payload.include_default_career_pages:
            default_greenhouse_boards, default_lever_sites = split_career_page_targets(DEFAULT_CAREER_PAGE_TARGETS)
            payload.greenhouse_boards.extend(
                board for board in default_greenhouse_boards if board not in payload.greenhouse_boards
            )
            payload.lever_sites.extend(site for site in default_lever_sites if site not in payload.lever_sites)

    for source in sources:
        if source == JobSource.GREENHOUSE:
            result = _collect_greenhouse(db, payload.greenhouse_boards)
        elif source == JobSource.LEVER:
            result = _collect_lever(db, payload.lever_sites)
        elif source == JobSource.LINKEDIN:
            result = _collect_linkedin(
                db,
                query=payload.query,
                location=payload.location,
                limit=payload.job_board_limit,
                date_posted=payload.date_posted,
                enrich_details=payload.linkedin_enrich_details,
                detail_limit=payload.linkedin_detail_limit,
            )
        elif source == JobSource.INDEED:
            result = _build_job_board_search(source, payload.query, payload.location, build_indeed_jobs_url)
        else:
            result = JobSourceCollectionResult(
                source=source,
                status="skipped",
                fetched=0,
                saved=0,
                message="Connector planned but not implemented yet.",
            )

        total_saved += result.saved
        results.append(result)

    return JobCollectionResult(total_saved=total_saved, results=results)


def _collect_linkedin(
    db: Session,
    *,
    query: str | None,
    location: str | None,
    limit: int,
    date_posted: str | None,
    enrich_details: bool,
    detail_limit: int,
) -> JobSourceCollectionResult:
    if not query:
        return JobSourceCollectionResult(
            source=JobSource.LINKEDIN,
            status="skipped",
            fetched=0,
            saved=0,
            message="Query is required for LinkedIn collection.",
            search_url=None,
        )

    try:
        jobs = fetch_linkedin_jobs(query=query, location=location, limit=limit, date_posted=date_posted)
    except Exception as exc:  # LinkedIn is best-effort and should not stop other connectors.
        return JobSourceCollectionResult(
            source=JobSource.LINKEDIN,
            status="error",
            fetched=0,
            saved=0,
            message=str(exc),
            search_url=build_linkedin_jobs_url(query, location),
        )

    enriched = 0
    enrichment_failed = 0
    if enrich_details and detail_limit:
        existing = get_jobs_by_external_ids(
            db,
            source="linkedin",
            external_ids=[job.external_id for job in jobs],
        )
        candidates = []
        for job in jobs:
            stored = existing.get(job.external_id)
            if stored is None or not stored.description:
                candidates.append(
                    job.model_copy(
                        update={
                            "details_attempts": (stored.details_attempts if stored else 0) + 1,
                            "details_status": "pending",
                        }
                    )
                )
            if len(candidates) >= detail_limit:
                break
        enriched_jobs, enriched, enrichment_failed = enrich_linkedin_jobs(candidates)
        enriched_by_id = {job.external_id: job for job in enriched_jobs}
        jobs = [enriched_by_id.get(job.external_id, job) for job in jobs]

    created, updated = upsert_jobs(db, jobs)

    return JobSourceCollectionResult(
        source=JobSource.LINKEDIN,
        status="completed",
        fetched=len(jobs),
        saved=created,
        created=created,
        updated=updated,
        enriched=enriched,
        enrichment_failed=enrichment_failed,
        message=None if jobs else "No LinkedIn jobs were returned for this search.",
        search_url=build_linkedin_jobs_url(query, location),
    )


def enrich_stored_linkedin_jobs(
    db: Session,
    payload: LinkedInEnrichmentRequest,
) -> LinkedInEnrichmentResult:
    stored_jobs = list_linkedin_jobs_needing_enrichment(db, limit=payload.limit)
    candidates = [
        JobCreate.model_validate(job, from_attributes=True).model_copy(
            update={
                "details_attempts": job.details_attempts + 1,
                "details_status": "pending",
            }
        )
        for job in stored_jobs
    ]
    enriched_jobs, enriched, failed = enrich_linkedin_jobs(candidates)
    upsert_jobs(db, enriched_jobs)
    return LinkedInEnrichmentResult(
        attempted=len(candidates),
        enriched=enriched,
        failed=failed,
        remaining=count_linkedin_jobs_needing_enrichment(db),
    )


def collect_company_jobs(db: Session, payload: CompanyJobCollectionRequest) -> CompanyJobCollectionResult:
    company = get_company_by_name(db, payload.company_name)
    if company is None:
        return CompanyJobCollectionResult(
            company=payload.company_name,
            careers_url=None,
            ats_type="unknown",
            ats_identifier=None,
            status="not_found",
            fetched=0,
            saved=0,
            message="Company is not in the career page index yet.",
        )

    if company.circuit_open_until and company.circuit_open_until > utc_now():
        return CompanyJobCollectionResult(
            company=company.name,
            careers_url=company.careers_url,
            ats_type=company.ats_type,
            ats_identifier=company.ats_identifier,
            status="circuit_open",
            fetched=0,
            saved=0,
            message=company.last_error or "Collection is temporarily paused after repeated failures.",
        )

    try:
        if company.ats_type in {"auto", "unknown", "generic", "custom"} and company.careers_url:
            detected = probe_ats(company.careers_url)
            company.ats_type = detected.ats_type
            company.ats_identifier = detected.identifier
            company.ats_confidence = detected.confidence
            db.commit()
        jobs = _fetch_company_jobs(company, limit=payload.limit)
    except Exception as exc:
        record_company_collection_failure(db, company, str(exc))
        return CompanyJobCollectionResult(
            company=company.name,
            careers_url=company.careers_url,
            ats_type=company.ats_type,
            ats_identifier=company.ats_identifier,
            status="error",
            fetched=0,
            saved=0,
            message=str(exc),
        )

    created, updated = upsert_jobs(db, jobs)
    record_company_collection_success(db, company, has_jobs=bool(jobs))

    _, stored_jobs = search_jobs_by_company(
        db,
        company=company.name,
        query=payload.query,
        location=payload.location,
        limit=payload.limit,
        offset=payload.offset,
    )

    return CompanyJobCollectionResult(
        company=company.name,
        careers_url=company.careers_url,
        ats_type=company.ats_type,
        ats_identifier=company.ats_identifier,
        status="completed",
        fetched=len(jobs),
        saved=created,
        created=created,
        updated=updated,
        message=None if jobs else "No public jobs were returned by this company source.",
        jobs=stored_jobs,
    )


def _fetch_company_jobs(company, *, limit: int) -> list[JobCreate]:
    if company.ats_type == "greenhouse" and company.ats_identifier:
        return fetch_greenhouse_jobs(
            company.ats_identifier,
            company_name=company.name,
            max_jobs=limit,
        )
    if company.ats_type == "lever" and company.ats_identifier:
        return fetch_lever_jobs(company.ats_identifier, company_name=company.name, max_jobs=limit)
    if company.ats_type == "ashby" and company.ats_identifier:
        return fetch_ashby_jobs(company.ats_identifier, company_name=company.name, max_jobs=limit)
    if company.ats_type == "smartrecruiters" and company.ats_identifier:
        return fetch_smartrecruiters_jobs(
            company.ats_identifier,
            company_name=company.name,
            max_jobs=min(limit, 100),
        )
    if company.ats_type == "workday" and company.careers_url:
        try:
            return fetch_workday_jobs(company.careers_url, company_name=company.name, max_jobs=min(limit, 100))
        except ConnectorFetchError as exc:
            if "Invalid Workday external career-site URL" not in str(exc):
                raise
            return fetch_generic_career_jobs(
                company.careers_url,
                company_name=company.name,
                max_jobs=min(limit, 50),
            )
    if company.careers_url:
        return fetch_generic_career_jobs(
            company.careers_url,
            company_name=company.name,
            max_jobs=min(limit, 50),
        )
    raise RuntimeError(f"{company.name} has no public career URL")


def _build_job_board_search(source: JobSource, query: str | None, location: str | None, builder) -> JobSourceCollectionResult:
    if not query:
        return JobSourceCollectionResult(
            source=source,
            status="skipped",
            fetched=0,
            saved=0,
            message="Query is required for this job board source.",
        )

    return JobSourceCollectionResult(
        source=source,
        status="browser_required",
        fetched=0,
        saved=0,
        message="Use this URL for browser-assisted collection. Direct scraping is not enabled for this source yet.",
        search_url=builder(query, location),
    )


def _collect_greenhouse(db: Session, board_tokens: list[str]) -> JobSourceCollectionResult:
    saved = 0
    fetched = 0
    errors: list[str] = []

    if not board_tokens:
        return JobSourceCollectionResult(
            source=JobSource.GREENHOUSE,
            status="skipped",
            fetched=0,
            saved=0,
            message="No Greenhouse board tokens provided.",
        )

    for board_token in board_tokens:
        try:
            jobs = fetch_greenhouse_jobs(board_token)
        except Exception as exc:  # Connector errors should not stop other sources.
            errors.append(f"{board_token}: {exc}")
            continue

        fetched += len(jobs)
        for job in jobs:
            upsert_job(db, job)
            saved += 1

    return JobSourceCollectionResult(
        source=JobSource.GREENHOUSE,
        status="error" if errors and saved == 0 else "completed",
        fetched=fetched,
        saved=saved,
        message="; ".join(errors) if errors else None,
    )


def _collect_lever(db: Session, sites: list[str]) -> JobSourceCollectionResult:
    saved = 0
    fetched = 0
    errors: list[str] = []

    if not sites:
        return JobSourceCollectionResult(
            source=JobSource.LEVER,
            status="skipped",
            fetched=0,
            saved=0,
            message="No Lever sites provided.",
        )

    for site in sites:
        try:
            jobs = fetch_lever_jobs(site)
        except Exception as exc:  # Connector errors should not stop other sources.
            errors.append(f"{site}: {exc}")
            continue

        fetched += len(jobs)
        for job in jobs:
            upsert_job(db, job)
            saved += 1

    return JobSourceCollectionResult(
        source=JobSource.LEVER,
        status="error" if errors and saved == 0 else "completed",
        fetched=fetched,
        saved=saved,
        message="; ".join(errors) if errors else None,
    )
