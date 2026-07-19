"""Full and fresh job collection runs."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from threading import Lock

from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.company import Company
from app.models.job import Job
from app.providers.catalog import COMPANY_SLUGS_BY_ENUM
from app.providers.sources import JobSource
from app.schemas.job import (
    CompanyJobCollectionRequest,
    CompanyJobCollectionResult,
    CompleteJobRunRequest,
    FreshJobRunRequest,
    JobCollectionRequest,
    JobRunResponse,
    JobSourceCollectionResult,
)
from app.services.company_service import seed_default_companies
from app.services.job_collection_service import collect_company_jobs, collect_jobs


JOB_BOARD_RUN_SOURCES = {
    JobSource.LINKEDIN,
    JobSource.INDEED,
    JobSource.NAUKRI,
    JobSource.FOUNDIT,
    JobSource.WELLFOUND,
    JobSource.YC_JOBS,
    JobSource.INSTAHYRE,
    JobSource.CUTSHORT,
    JobSource.HIRIST,
}


def run_complete_job_collection(db: Session, payload: CompleteJobRunRequest) -> JobRunResponse:
    return _run_job_collection(db, payload, mode="complete")


def run_fresh_job_collection(db: Session, payload: FreshJobRunRequest) -> JobRunResponse:
    return _run_job_collection(db, payload, mode="fresh")


def _run_job_collection(
    db: Session,
    payload: CompleteJobRunRequest | FreshJobRunRequest,
    *,
    mode: str,
) -> JobRunResponse:
    seed_default_companies(db)

    company_names = _selected_company_names(db, payload) if payload.include_companies else []
    company_results = _collect_companies(db, company_names, payload)

    source_results: list[JobSourceCollectionResult] = []
    if payload.include_job_boards:
        source_results = _collect_job_board_searches(db, payload)

    totals = _summarize(db, company_results, source_results)
    return JobRunResponse(
        status="completed" if totals["failed"] == 0 else "completed_with_errors",
        mode=mode,
        companies_attempted=len(company_names),
        searches_attempted=len(payload.searches) if payload.include_job_boards else 0,
        total_fetched=totals["fetched"],
        total_saved=totals["saved"],
        total_created=totals["created"],
        total_updated=totals["updated"],
        total_enriched=totals["enriched"],
        total_failed=totals["failed"],
        total_skipped=totals["skipped"],
        total_unsupported=totals["unsupported"],
        jobs_with_descriptions=totals["jobs_with_descriptions"],
        jobs_missing_descriptions=totals["jobs_missing_descriptions"],
        jobs_with_jd=totals["jobs_with_descriptions"],
        jobs_without_jd=totals["jobs_missing_descriptions"],
        jd_coverage_percent=_coverage_percent(totals),
        coverage_notes=_coverage_notes(totals),
        error_summary=_error_summary(company_results, source_results),
        company_results=company_results,
        source_results=source_results,
        message=_message_for(mode),
    )


def _selected_company_names(
    db: Session,
    payload: CompleteJobRunRequest | FreshJobRunRequest,
) -> list[str]:
    query = db.query(Company).filter(Company.is_active.is_(True))

    if payload.companies:
        slugs = [COMPANY_SLUGS_BY_ENUM[company] for company in payload.companies]
        query = query.filter(Company.slug.in_(slugs))

    if payload.ats_platforms:
        ats_types = [platform.value for platform in payload.ats_platforms]
        query = query.filter(Company.ats_type.in_(ats_types))

    return [company.name for company in query.order_by(Company.name.asc()).all()]


def _collect_companies(
    db: Session,
    company_names: list[str],
    payload: CompleteJobRunRequest | FreshJobRunRequest,
) -> list[CompanyJobCollectionResult]:
    if not company_names:
        return []

    if payload.max_parallel_company_runs == 1:
        return [
            collect_company_jobs(
                db,
                CompanyJobCollectionRequest(company_name=name, limit=payload.company_job_limit),
            )
            for name in company_names
        ]

    results: list[CompanyJobCollectionResult] = []
    workers = min(payload.max_parallel_company_runs, len(company_names))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_collect_company_with_new_session, name, payload.company_job_limit): name
            for name in company_names
        }
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:
                results.append(
                    CompanyJobCollectionResult(
                        company=futures[future],
                        careers_url=None,
                        ats_type="unknown",
                        ats_identifier=None,
                        status="error",
                        fetched=0,
                        saved=0,
                        message=str(exc),
                    )
                )
    return sorted(results, key=lambda result: result.company.lower())


def _collect_job_board_searches(
    db: Session,
    payload: CompleteJobRunRequest | FreshJobRunRequest,
) -> list[JobSourceCollectionResult]:
    sources = [source for source in payload.sources if source in JOB_BOARD_RUN_SOURCES]
    if not sources or not payload.searches:
        return []

    tasks = [(source, search.query, search.location) for source in sources for search in payload.searches]
    pacer = _SearchPacer(payload.job_board_request_delay_seconds)
    if payload.max_parallel_search_runs == 1:
        results = [
            _collect_source(db, source, query, location, payload, pacer)
            for source, query, location in tasks
        ]
        return results

    results: list[JobSourceCollectionResult] = []
    workers = min(payload.max_parallel_search_runs, len(tasks))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_collect_source_with_new_session, source, query, location, payload, pacer): (source, query, location)
            for source, query, location in tasks
        }
        for future in as_completed(futures):
            source, query, location = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append(
                    JobSourceCollectionResult(
                        source=source,
                        status="error",
                        fetched=0,
                        saved=0,
                        message=f"{query} / {location or 'anywhere'}: {exc}",
                    )
                )
    return results


def _collect_company_with_new_session(company_name: str, limit: int) -> CompanyJobCollectionResult:
    db = SessionLocal()
    try:
        return collect_company_jobs(db, CompanyJobCollectionRequest(company_name=company_name, limit=limit))
    finally:
        db.close()


def _collect_source_with_new_session(
    source: JobSource,
    query: str,
    location: str | None,
    payload: CompleteJobRunRequest | FreshJobRunRequest,
    pacer: "_SearchPacer",
) -> JobSourceCollectionResult:
    db = SessionLocal()
    try:
        return _collect_source(db, source, query, location, payload, pacer)
    finally:
        db.close()


def _collect_source(
    db: Session,
    source: JobSource,
    query: str,
    location: str | None,
    payload: CompleteJobRunRequest | FreshJobRunRequest,
    pacer: "_SearchPacer",
) -> JobSourceCollectionResult:
    pacer.wait()
    collection = collect_jobs(
        db,
        JobCollectionRequest(
            sources=[source],
            query=query,
            location=location,
            job_board_limit=payload.job_board_limit,
            date_posted=payload.date_posted,
            linkedin_enrich_details=payload.linkedin_enrich_details,
            linkedin_detail_limit=payload.linkedin_detail_limit,
            include_default_career_pages=False,
        ),
    )
    result = collection.results[0]
    if result.message:
        result.message = f"{query} / {location or 'anywhere'}: {result.message}"
    else:
        result.message = f"{query} / {location or 'anywhere'}"
    return result


class _SearchPacer:
    def __init__(self, min_interval: float) -> None:
        self.min_interval = min_interval
        self._lock = Lock()
        self._next_at = 0.0

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            if now < self._next_at:
                time.sleep(self._next_at - now)
            self._next_at = time.monotonic() + self.min_interval


def _summarize(
    db: Session,
    company_results: list[CompanyJobCollectionResult],
    source_results: list[JobSourceCollectionResult],
) -> dict[str, int]:
    failed = 0
    skipped = 0
    unsupported = 0
    for result in company_results:
        if result.status in {"error", "circuit_open"}:
            failed += 1
        elif result.status in {"skipped", "not_found"}:
            skipped += 1
    for result in source_results:
        if result.status == "error":
            failed += 1
        elif result.status == "skipped":
            skipped += 1
            if result.message and "not implemented" in result.message:
                unsupported += 1

    return {
        "fetched": sum(result.fetched for result in company_results)
        + sum(result.fetched for result in source_results),
        "saved": sum(result.saved for result in company_results) + sum(result.saved for result in source_results),
        "created": sum(result.created for result in company_results)
        + sum(result.created for result in source_results),
        "updated": sum(result.updated for result in company_results)
        + sum(result.updated for result in source_results),
        "enriched": sum(result.enriched for result in source_results),
        "failed": failed,
        "skipped": skipped,
        "unsupported": unsupported,
        "jobs_with_descriptions": db_description_count(db, company_results, source_results, has_description=True),
        "jobs_missing_descriptions": db_description_count(db, company_results, source_results, has_description=False),
    }


def db_description_count(
    db: Session,
    company_results: list[CompanyJobCollectionResult],
    source_results: list[JobSourceCollectionResult],
    *,
    has_description: bool,
) -> int:
    sources = {str(result.source.value) for result in source_results if result.fetched > 0}
    sources.update(result.ats_type for result in company_results if result.fetched > 0)
    if not sources:
        return 0

    query = db.query(Job).filter(Job.source.in_(sources))
    if has_description:
        query = query.filter(Job.description.is_not(None))
    else:
        query = query.filter(Job.description.is_(None))
    return query.count()


def _coverage_notes(totals: dict[str, int]) -> list[str]:
    notes = [
        "total_enriched counts only jobs that required a separate detail-enrichment step, mainly LinkedIn.",
        "ATS and career-page jobs often arrive with descriptions already included, so they improve description coverage without increasing total_enriched.",
    ]
    if totals["unsupported"]:
        notes.append(
            f"{totals['unsupported']} source/search runs were skipped because those source connectors are planned but not implemented yet."
        )
    if totals["jobs_with_descriptions"] or totals["jobs_missing_descriptions"]:
        total = totals["jobs_with_descriptions"] + totals["jobs_missing_descriptions"]
        percent = round((totals["jobs_with_descriptions"] / total) * 100, 1)
        notes.append(f"{percent}% of stored jobs from this run's active sources currently have descriptions.")
    return notes


def _coverage_percent(totals: dict[str, int]) -> float:
    total = totals["jobs_with_descriptions"] + totals["jobs_missing_descriptions"]
    if total == 0:
        return 0.0
    return round((totals["jobs_with_descriptions"] / total) * 100, 1)


def _error_summary(
    company_results: list[CompanyJobCollectionResult],
    source_results: list[JobSourceCollectionResult],
) -> list[str]:
    errors: list[str] = []
    for result in company_results:
        if result.status in {"error", "circuit_open"}:
            errors.append(f"company:{result.company} [{result.ats_type}] {result.status}: {result.message or 'no detail'}")
    for result in source_results:
        if result.status == "error":
            errors.append(f"source:{result.source.value} {result.status}: {result.message or 'no detail'}")
    return errors[:50]


def _message_for(mode: str) -> str:
    if mode == "fresh":
        return (
            "Fresh run finished. Job boards use the requested freshness window where supported; "
            "career pages were rechecked and deduped against stored jobs."
        )
    return (
        "Complete run finished. Company career sources and configured job-board searches were processed "
        "with bounded parallelism."
    )
