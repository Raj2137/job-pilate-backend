"""Web discovery service for candidate job application links."""

from app.providers.sources import JobSource
from app.providers.web_search_providers import search_web
from app.schemas.job import JobDiscoveryRequest, JobDiscoveryResponse, JobDiscoverySourceResult


def discover_jobs(payload: JobDiscoveryRequest) -> JobDiscoveryResponse:
    results: list[JobDiscoverySourceResult] = []
    total_found = 0

    for source in payload.sources:
        try:
            provider_result = search_web(source, payload.query, payload.location, payload.limit_per_source)
            links = provider_result.items
        except Exception as exc:
            results.append(
                JobDiscoverySourceResult(
                    source=source,
                    status="error",
                    found=0,
                    message=str(exc),
                    items=[],
                )
            )
            continue

        total_found += len(links)
        results.append(
            JobDiscoverySourceResult(
                source=source,
                status="completed" if links else "no_results",
                found=len(links),
                message=f"provider={provider_result.provider}" if links else f"provider={provider_result.provider}; no candidate links found",
                items=links,
            )
        )

    return JobDiscoveryResponse(total_found=total_found, results=results)
