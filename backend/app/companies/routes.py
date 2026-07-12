"""Company career source routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.company import CompanyRead, CompanyResolveRequest, CompanySearchResponse
from app.services.company_service import register_company, resolve_company, search_companies

router = APIRouter()


@router.get("", response_model=CompanySearchResponse)
def list_company_sources(
    query: str | None = Query(default=None),
    industry: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CompanySearchResponse:
    return search_companies(db, query=query, industry=industry, limit=limit, offset=offset)


@router.post("", response_model=CompanyRead)
def register_company_source(
    payload: CompanyResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CompanyRead:
    return register_company(
        db,
        name=payload.name,
        website_url=str(payload.website_url) if payload.website_url else None,
        careers_url=str(payload.careers_url),
        industry=payload.industry,
    )


@router.get("/resolve", response_model=CompanyRead | None)
def resolve_company_source(
    name: str = Query(min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CompanyRead | None:
    return resolve_company(db, name)
