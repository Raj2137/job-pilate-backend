from unittest import TestCase
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.session import Base
from app.models.company import Company
from app.providers.http import ConnectorFetchError
from app.schemas.job import CompanyJobCollectionRequest, JobCreate
from app.services.job_collection_service import collect_company_jobs


class CompanyCollectionTests(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.company = Company(
            name="Example",
            slug="example",
            domain="example.com",
            careers_url="https://careers.example.com",
            ats_type="oracle",
            is_active=True,
        )
        self.db.add(self.company)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    @patch("app.services.job_collection_service._fetch_company_jobs")
    def test_opens_circuit_after_three_failures(self, fetch_jobs) -> None:
        fetch_jobs.side_effect = RuntimeError("source unavailable")
        payload = CompanyJobCollectionRequest(company_name="Example")

        results = [collect_company_jobs(self.db, payload) for _ in range(3)]
        blocked = collect_company_jobs(self.db, payload)

        self.assertTrue(all(result.status == "error" for result in results))
        self.assertEqual("circuit_open", blocked.status)
        self.assertEqual(3, fetch_jobs.call_count)
        self.db.refresh(self.company)
        self.assertEqual("circuit_open", self.company.collection_status)
        self.assertIsNotNone(self.company.circuit_open_until)

    @patch("app.services.job_collection_service.fetch_generic_career_jobs")
    @patch("app.services.job_collection_service.fetch_workday_jobs")
    def test_invalid_workday_url_falls_back_to_generic_career_page(self, fetch_workday_jobs, fetch_generic_career_jobs) -> None:
        self.company.ats_type = "workday"
        self.company.careers_url = "https://careers.example.com/search"
        self.db.commit()
        fetch_workday_jobs.side_effect = ConnectorFetchError("Invalid Workday external career-site URL")
        fetch_generic_career_jobs.return_value = [
            JobCreate(
                source="career_page",
                external_id="example-1",
                title="Backend Engineer",
                company="Example",
                description="Build APIs.",
            )
        ]

        result = collect_company_jobs(self.db, CompanyJobCollectionRequest(company_name="Example"))

        self.assertEqual("completed", result.status)
        self.assertEqual(1, result.fetched)
        self.assertEqual(1, result.saved)
        fetch_generic_career_jobs.assert_called_once()
