"""Database engine and session helpers."""

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import get_settings

settings = get_settings()
engine_args = {"connect_args": {"check_same_thread": False}} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, **engine_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_db_and_tables() -> None:
    from app.models import application, company, job, llm_key, search_segment, user  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _add_missing_user_columns()
    _add_missing_job_columns()
    _add_missing_company_columns()
    _add_missing_search_segment_columns()


def _add_missing_user_columns() -> None:
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("users")}
    additions = {
        "auth_provider": "VARCHAR(50) NOT NULL DEFAULT 'password'",
        "google_sub": "VARCHAR(255)",
        "picture": "VARCHAR(500)",
    }
    with engine.begin() as connection:
        for name, column_type in additions.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE users ADD COLUMN {name} {column_type}"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_sub ON users (google_sub)"))


def _add_missing_job_columns() -> None:
    """Keep existing development databases usable until Alembic is introduced."""
    inspector = inspect(engine)
    if "jobs" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("jobs")}
    additions = {
        "seniority_level": "VARCHAR(100)",
        "application_method": "VARCHAR(32)",
        "company_url": "TEXT",
        "details_status": "VARCHAR(32)",
        "details_attempts": "INTEGER NOT NULL DEFAULT 0",
        "details_error": "TEXT",
        "details_fetched_at": "DATETIME",
    }
    with engine.begin() as connection:
        for name, column_type in additions.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE jobs ADD COLUMN {name} {column_type}"))
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_jobs_application_method ON jobs (application_method)")
        )
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_jobs_details_status ON jobs (details_status)"))
        connection.execute(
            text(
                "UPDATE jobs SET details_status = 'complete', "
                "details_fetched_at = COALESCE(details_fetched_at, updated_at) "
                "WHERE source = 'linkedin' AND description IS NOT NULL AND details_status IS NULL"
            )
        )


def _add_missing_company_columns() -> None:
    inspector = inspect(engine)
    if "companies" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("companies")}
    additions = {
        "industry": "VARCHAR(100)",
        "ats_confidence": "VARCHAR(32)",
        "application_mode": "VARCHAR(32) NOT NULL DEFAULT 'assisted'",
        "collection_status": "VARCHAR(32) NOT NULL DEFAULT 'pending'",
        "consecutive_failures": "INTEGER NOT NULL DEFAULT 0",
        "circuit_open_until": "DATETIME",
        "last_success_at": "DATETIME",
        "last_error": "TEXT",
    }
    with engine.begin() as connection:
        for name, column_type in additions.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE companies ADD COLUMN {name} {column_type}"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_companies_industry ON companies (industry)"))
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_companies_collection_status ON companies (collection_status)")
        )


def _add_missing_search_segment_columns() -> None:
    inspector = inspect(engine)
    if "search_segments" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("search_segments")}
    additions = {
        "initial_date_posted": "VARCHAR(32) NOT NULL DEFAULT 'past_week'",
        "incremental_date_posted": "VARCHAR(32) NOT NULL DEFAULT 'past_24h'",
    }
    with engine.begin() as connection:
        for name, column_type in additions.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE search_segments ADD COLUMN {name} {column_type}"))
