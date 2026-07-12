"""Company career source service."""

from sqlalchemy.orm import Session
from urllib.parse import urlparse

from app.providers.ats_detection import detect_ats
from app.providers.generic_career import require_public_url
from app.providers.company_index import COMPANY_SEEDS
from app.repositories.company_repository import get_company_by_name, list_companies, upsert_company
from app.schemas.company import CompanyRead, CompanySearchResponse


def seed_default_companies(db: Session) -> None:
    for seed in COMPANY_SEEDS:
        detected = detect_ats(seed.careers_url)
        ats_type = detected.ats_type if seed.ats_type == "auto" else seed.ats_type
        identifier = seed.ats_identifier or (detected.identifier if seed.ats_type == "auto" else None)
        upsert_company(
            db,
            name=seed.name,
            domain=seed.domain,
            industry=seed.industry,
            careers_url=seed.careers_url,
            ats_type=ats_type,
            ats_identifier=identifier,
            ats_confidence=detected.confidence if seed.ats_type == "auto" else "curated",
        )


def search_companies(
    db: Session,
    *,
    query: str | None = None,
    industry: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> CompanySearchResponse:
    total, companies = list_companies(db, query=query, industry=industry, limit=limit, offset=offset)
    return CompanySearchResponse(total=total, limit=limit, offset=offset, items=companies)


def resolve_company(db: Session, name: str) -> CompanyRead | None:
    return get_company_by_name(db, name)


def register_company(db: Session, *, name: str, website_url: str | None, careers_url: str, industry: str | None):
    require_public_url(careers_url)
    detected = detect_ats(careers_url)
    domain = urlparse(website_url or careers_url).hostname
    return upsert_company(
        db,
        name=name,
        domain=domain,
        industry=industry,
        careers_url=careers_url,
        ats_type=detected.ats_type,
        ats_identifier=detected.identifier,
        ats_confidence=detected.confidence,
    )
