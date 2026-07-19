"""Run the dedicated JobPilot collection worker."""

import argparse
from dataclasses import asdict

from app.core.config import get_settings
from app.database.session import SessionLocal, create_db_and_tables
from app.repositories.search_segment_repository import ensure_company_segments
from app.scheduler.job_scheduler import run_scheduler_cycle, run_scheduler_forever
from app.services.company_service import seed_default_companies


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the JobPilot collection worker")
    parser.add_argument("--once", action="store_true", help="Run one scheduler cycle and exit")
    args = parser.parse_args()
    if not args.once:
        run_scheduler_forever()
        return

    settings = get_settings()
    create_db_and_tables()
    db = SessionLocal()
    try:
        seed_default_companies(db)
        ensure_company_segments(db, interval_minutes=settings.job_collection_interval_minutes)
        result = run_scheduler_cycle(
            db,
            worker_id="manual-once",
            batch_size=settings.scheduler_batch_size,
            lease_minutes=settings.scheduler_lease_minutes,
            enrichment_batch_size=settings.linkedin_enrichment_batch_size,
        )
        print(asdict(result))
    finally:
        db.close()


if __name__ == "__main__":
    main()
