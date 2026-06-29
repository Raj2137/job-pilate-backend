"""FastAPI application factory."""

from fastapi import FastAPI

from app.api.router import api_router
from app.database.session import create_db_and_tables


app = FastAPI(title="JobPilot API", version="0.1.0")


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router, prefix="/api")
