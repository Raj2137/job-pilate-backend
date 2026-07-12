"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.database.session import create_db_and_tables
from app.database.session import SessionLocal
from app.services.company_service import seed_default_companies


app = FastAPI(title="JobPilot API", version="0.1.0")
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()
    db = SessionLocal()
    try:
        seed_default_companies(db)
    finally:
        db.close()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router, prefix="/api")
