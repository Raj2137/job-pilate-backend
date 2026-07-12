from unittest import TestCase
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.session import Base
from app.models.company import Company
from app.models.search_segment import SearchSegment
from app.providers.catalog import LaunchCompany, MajorAtsPlatform
from app.providers.sources import JobSource
from app.schemas.job import CatalogCollectionRequest, CatalogLinkedInSearch
from app.services.catalog_collection_service import trigger_catalog_collection


class CatalogCollectionTests(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_trigger_creates_filtered_company_and_linkedin_segments(self) -> None:
        response = trigger_catalog_collection(
            self.db,
            CatalogCollectionRequest(
                companies=[LaunchCompany.STRIPE, LaunchCompany.NOTION],
                ats_platforms=[MajorAtsPlatform.GREENHOUSE],
                linkedin_searches=[CatalogLinkedInSearch(query="software engineer", location="India")],
                initial_date_posted="past_month",
                incremental_date_posted="past_24h",
                run_now=False,
            ),
        )

        company_segments = self.db.query(SearchSegment).filter(SearchSegment.company_id.is_not(None)).all()
        linkedin_segments = self.db.query(SearchSegment).filter(SearchSegment.source == JobSource.LINKEDIN).all()
        companies = {self.db.get(Company, segment.company_id).name for segment in company_segments}

        self.assertEqual("scheduled", response.status)
        self.assertEqual({"Stripe"}, companies)
        self.assertEqual(1, len(linkedin_segments))
        self.assertEqual("past_month", linkedin_segments[0].initial_date_posted)
        self.assertEqual("past_24h", linkedin_segments[0].incremental_date_posted)
        self.assertGreaterEqual(response.due_segments, 2)

    @patch("app.services.catalog_collection_service.run_scheduler_cycle")
    def test_run_now_processes_a_controlled_batch(self, run_scheduler_cycle) -> None:
        run_scheduler_cycle.return_value.claimed = 2
        run_scheduler_cycle.return_value.completed = 1
        run_scheduler_cycle.return_value.failed = 1

        response = trigger_catalog_collection(
            self.db,
            CatalogCollectionRequest(
                include_companies=False,
                linkedin_searches=[CatalogLinkedInSearch(query="backend engineer", location="India")],
                run_now=True,
                run_batch_size=2,
            ),
        )

        self.assertEqual("started", response.status)
        self.assertEqual(2, response.scheduler_claimed)
        self.assertEqual(1, response.scheduler_completed)
        self.assertEqual(1, response.scheduler_failed)
        self.assertEqual(2, run_scheduler_cycle.call_args.kwargs["batch_size"])
