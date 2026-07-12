from unittest import TestCase

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.session import Base
from app.models.job import Job
from app.repositories.job_repository import upsert_jobs
from app.schemas.job import JobCreate


class JobRepositoryTests(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_bulk_upsert_counts_and_preserves_enriched_fields(self) -> None:
        enriched = JobCreate(
            source="linkedin",
            external_id="123",
            title="Software Engineer",
            company="Example Co",
            description="Build reliable APIs.",
            application_method="external",
            details_status="complete",
            details_attempts=1,
        )
        created, updated = upsert_jobs(self.db, [enriched])

        card_only_update = enriched.model_copy(
            update={"title": "Backend Engineer", "description": None, "application_method": None}
        )
        second_created, second_updated = upsert_jobs(self.db, [card_only_update])
        stored = self.db.query(Job).filter(Job.external_id == "123").one()

        self.assertEqual((1, 0), (created, updated))
        self.assertEqual((0, 1), (second_created, second_updated))
        self.assertEqual("Backend Engineer", stored.title)
        self.assertEqual("Build reliable APIs.", stored.description)
        self.assertEqual("external", stored.application_method)
        self.assertEqual("complete", stored.details_status)
        self.assertEqual(1, stored.details_attempts)
