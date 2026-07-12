"""Company career source persistence helpers."""

import re
from datetime import timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.company import Company
from app.repositories.search_segment_repository import utc_now


def slugify_company_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or name.lower().strip()


def get_company_by_slug(db: Session, slug: str) -> Company | None:
    return db.query(Company).filter(Company.slug == slug).first()


def get_company_by_name(db: Session, name: str) -> Company | None:
    return get_company_by_slug(db, slugify_company_name(name))


def list_companies(
    db: Session,
    *,
    query: str | None = None,
    industry: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[int, list[Company]]:
    stmt = db.query(Company)
    if query:
        pattern = f"%{query.strip()}%"
        stmt = stmt.filter(or_(Company.name.ilike(pattern), Company.domain.ilike(pattern)))
    if industry:
        stmt = stmt.filter(Company.industry == industry.strip().lower())
    stmt = stmt.order_by(Company.name.asc())
    return stmt.count(), stmt.offset(offset).limit(limit).all()


def upsert_company(
    db: Session,
    *,
    name: str,
    domain: str | None,
    careers_url: str | None,
    ats_type: str,
    ats_identifier: str | None,
    industry: str | None = None,
    ats_confidence: str | None = None,
    application_mode: str = "assisted",
    is_active: bool = True,
) -> Company:
    slug = slugify_company_name(name)
    company = get_company_by_slug(db, slug)
    values = {
        "name": name,
        "slug": slug,
        "domain": domain,
        "industry": industry,
        "careers_url": careers_url,
        "ats_type": ats_type,
        "ats_identifier": ats_identifier,
        "ats_confidence": ats_confidence,
        "application_mode": application_mode,
        "is_active": is_active,
    }

    if company is None:
        company = Company(**values)
        db.add(company)
    else:
        for key, value in values.items():
            setattr(company, key, value)

    db.commit()
    db.refresh(company)
    return company


def record_company_collection_success(db: Session, company: Company, *, has_jobs: bool) -> None:
    now = utc_now()
    company.collection_status = "healthy" if has_jobs else "empty"
    company.consecutive_failures = 0
    company.circuit_open_until = None
    company.last_checked_at = now
    company.last_success_at = now
    company.last_error = None
    db.commit()


def record_company_collection_failure(
    db: Session,
    company: Company,
    error: str,
    *,
    failure_threshold: int = 3,
    circuit_minutes: int = 60,
) -> None:
    now = utc_now()
    company.consecutive_failures += 1
    company.last_checked_at = now
    company.last_error = error[:2000]
    if company.consecutive_failures >= failure_threshold:
        company.collection_status = "circuit_open"
        company.circuit_open_until = now + timedelta(minutes=circuit_minutes)
    else:
        company.collection_status = "degraded"
    db.commit()
