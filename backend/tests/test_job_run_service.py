from unittest import TestCase
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.session import Base
from app.models.company import Company
from app.models.job import Job
from app.providers.catalog import LaunchCompany
from app.providers.sources import JobSource
from app.schemas.job import (
    CompanyJobCollectionResult,
    CompleteJobRunRequest,
    FreshJobRunRequest,
    JobCollectionResult,
    JobRunSearch,
    JobSourceCollectionResult,
)
from app.services.job_run_service import run_complete_job_collection, run_fresh_job_collection


class JobRunServiceTests(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add_all(
            [
                Company(
                    name="Stripe",
                    slug="stripe",
                    ats_type="greenhouse",
                    ats_identifier="stripe",
                    is_active=True,
                ),
                Company(
                    name="Notion",
                    slug="notion",
                    ats_type="lever",
                    ats_identifier="notion",
                    is_active=True,
                ),
            ]
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    @patch("app.services.job_run_service.seed_default_companies")
    @patch("app.services.job_run_service.collect_jobs")
    @patch("app.services.job_run_service.collect_company_jobs")
    def test_complete_run_uses_company_enum_and_job_board_searches(
        self,
        collect_company_jobs,
        collect_jobs,
        seed_default_companies,
    ) -> None:
        collect_company_jobs.return_value = CompanyJobCollectionResult(
            company="Stripe",
            careers_url="https://stripe.com/jobs",
            ats_type="greenhouse",
            ats_identifier="stripe",
            status="completed",
            fetched=10,
            saved=7,
            created=7,
            updated=3,
        )
        collect_jobs.return_value = JobCollectionResult(
            total_saved=5,
            results=[
                JobSourceCollectionResult(
                    source=JobSource.LINKEDIN,
                    status="completed",
                    fetched=8,
                    saved=5,
                    created=5,
                    updated=3,
                    enriched=4,
                )
            ],
        )

        response = run_complete_job_collection(
            self.db,
            CompleteJobRunRequest(
                companies=[LaunchCompany.STRIPE],
                sources=[JobSource.CAREER_PAGES, JobSource.LINKEDIN],
                searches=[JobRunSearch(query="software engineer", location="India")],
                max_parallel_company_runs=1,
                max_parallel_search_runs=1,
                job_board_request_delay_seconds=0,
            ),
        )

        self.assertEqual("completed", response.status)
        self.assertEqual(1, response.companies_attempted)
        self.assertEqual(1, response.searches_attempted)
        self.assertEqual(18, response.total_fetched)
        self.assertEqual(12, response.total_saved)
        self.assertEqual("Stripe", collect_company_jobs.call_args.args[1].company_name)
        self.assertEqual(JobSource.LINKEDIN, collect_jobs.call_args.args[1].sources[0])
        self.assertEqual("past_month", collect_jobs.call_args.args[1].date_posted)
        seed_default_companies.assert_called_once()

    @patch("app.services.job_run_service.seed_default_companies")
    @patch("app.services.job_run_service.collect_jobs")
    def test_fresh_run_defaults_to_past_24h_for_job_boards(
        self,
        collect_jobs,
        seed_default_companies,
    ) -> None:
        collect_jobs.return_value = JobCollectionResult(
            total_saved=1,
            results=[
                JobSourceCollectionResult(
                    source=JobSource.LINKEDIN,
                    status="completed",
                    fetched=2,
                    saved=1,
                    created=1,
                )
            ],
        )

        run_fresh_job_collection(
            self.db,
            FreshJobRunRequest(
                include_companies=False,
                sources=[JobSource.LINKEDIN],
                searches=[JobRunSearch(query="backend engineer", location="India")],
                max_parallel_search_runs=1,
                job_board_request_delay_seconds=0,
            ),
        )

        self.assertEqual("past_24h", collect_jobs.call_args.args[1].date_posted)
        seed_default_companies.assert_called_once()

    @patch("app.services.job_run_service.seed_default_companies")
    @patch("app.services.job_run_service.collect_jobs")
    def test_errors_are_summarized_by_source(
        self,
        collect_jobs,
        seed_default_companies,
    ) -> None:
        collect_jobs.return_value = JobCollectionResult(
            total_saved=0,
            results=[
                JobSourceCollectionResult(
                    source=JobSource.LINKEDIN,
                    status="error",
                    fetched=0,
                    saved=0,
                    message="rate limited",
                )
            ],
        )

        response = run_complete_job_collection(
            self.db,
            CompleteJobRunRequest(
                include_companies=False,
                sources=[JobSource.LINKEDIN],
                searches=[JobRunSearch(query="backend engineer", location="India")],
                max_parallel_search_runs=1,
                job_board_request_delay_seconds=0,
            ),
        )

        self.assertEqual("completed_with_errors", response.status)
        self.assertEqual(1, response.total_failed)
        self.assertEqual(["source:linkedin error: backend engineer / India: rate limited"], response.error_summary)

    @patch("app.services.job_run_service.seed_default_companies")
    @patch("app.services.job_run_service.collect_jobs")
    def test_jd_counts_are_returned(
        self,
        collect_jobs,
        seed_default_companies,
    ) -> None:
        self.db.add_all(
            [
                Job(
                    source="linkedin",
                    external_id="with-jd",
                    title="Backend Engineer",
                    company="Example",
                    description="Build APIs.",
                ),
                Job(
                    source="linkedin",
                    external_id="without-jd",
                    title="Frontend Engineer",
                    company="Example",
                    description=None,
                ),
            ]
        )
        self.db.commit()
        collect_jobs.return_value = JobCollectionResult(
            total_saved=0,
            results=[
                JobSourceCollectionResult(
                    source=JobSource.LINKEDIN,
                    status="completed",
                    fetched=2,
                    saved=0,
                )
            ],
        )

        response = run_complete_job_collection(
            self.db,
            CompleteJobRunRequest(
                include_companies=False,
                sources=[JobSource.LINKEDIN],
                searches=[JobRunSearch(query="engineer", location="India")],
                max_parallel_search_runs=1,
                job_board_request_delay_seconds=0,
            ),
        )

        self.assertEqual(1, response.jobs_with_jd)
        self.assertEqual(1, response.jobs_without_jd)
        self.assertEqual(50.0, response.jd_coverage_percent)
