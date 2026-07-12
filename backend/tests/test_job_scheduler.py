from datetime import timedelta
from unittest import TestCase
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.session import Base
from app.providers.sources import JobSource
from app.repositories.search_segment_repository import (
    claim_due_segments,
    ensure_linkedin_segment,
    make_segment_due,
    utc_now,
)
from app.scheduler.job_scheduler import run_scheduler_cycle
from app.schemas.job import JobCollectionResult, JobSourceCollectionResult
from app.schemas.search_segment import SearchSegmentCreate


class JobSchedulerTests(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_canonical_segment_is_reused(self) -> None:
        first = ensure_linkedin_segment(
            self.db,
            SearchSegmentCreate(query=" Software   Engineer ", location=" Bengaluru "),
        )
        second = ensure_linkedin_segment(
            self.db,
            SearchSegmentCreate(query="software engineer", location="bengaluru"),
        )

        self.assertEqual(first.id, second.id)
        self.assertEqual("software engineer", second.query)
        self.assertEqual("bengaluru", second.location)

    def test_lease_prevents_two_workers_claiming_same_segment(self) -> None:
        ensure_linkedin_segment(self.db, SearchSegmentCreate(query="backend engineer", location="India"))

        first = claim_due_segments(self.db, worker_id="worker-1", limit=5, lease_minutes=15)
        second = claim_due_segments(self.db, worker_id="worker-2", limit=5, lease_minutes=15)

        self.assertEqual(1, len(first))
        self.assertEqual([], second)

    @patch("app.scheduler.job_scheduler.collect_jobs")
    def test_first_run_backfills_week_then_uses_hourly_incremental_window(self, collect_jobs) -> None:
        segment = ensure_linkedin_segment(
            self.db,
            SearchSegmentCreate(
                query="software engineer",
                location="India",
                interval_minutes=60,
                job_limit=50,
            ),
        )
        collect_jobs.return_value = JobCollectionResult(
            total_saved=2,
            results=[
                JobSourceCollectionResult(
                    source=JobSource.LINKEDIN,
                    status="completed",
                    fetched=5,
                    saved=2,
                    created=2,
                    updated=3,
                    enriched=5,
                )
            ],
        )

        first = run_scheduler_cycle(
            self.db,
            worker_id="worker-1",
            batch_size=1,
            lease_minutes=15,
        )
        first_payload = collect_jobs.call_args.args[1]
        self.db.refresh(segment)

        self.assertEqual((1, 1, 0), (first.claimed, first.completed, first.failed))
        self.assertEqual("past_week", first_payload.date_posted)
        self.assertEqual(50, first_payload.job_board_limit)
        self.assertEqual(1, segment.run_count)
        self.assertGreaterEqual(segment.next_run_at, utc_now() + timedelta(minutes=59))

        make_segment_due(self.db, segment)
        run_scheduler_cycle(
            self.db,
            worker_id="worker-1",
            batch_size=1,
            lease_minutes=15,
        )
        second_payload = collect_jobs.call_args.args[1]

        self.assertEqual("past_24h", second_payload.date_posted)
        self.assertEqual(2, segment.run_count)
