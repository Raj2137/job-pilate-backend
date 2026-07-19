from unittest import TestCase
from unittest.mock import patch

from app.providers.http import ConnectorFetchError
from app.providers.linkedin import _parse_job_detail, enrich_linkedin_jobs, fetch_linkedin_jobs
from app.schemas.job import JobCreate


def _cards(start: int, count: int) -> str:
    return "".join(
        f"""
        <li>
          <div data-entity-urn="urn:li:jobPosting:{job_id}">
            <a class="base-card__full-link" href="https://in.linkedin.com/jobs/view/test-{job_id}"></a>
            <h3 class="base-search-card__title">Software Engineer {job_id}</h3>
            <h4 class="base-search-card__subtitle">Example Co</h4>
            <span class="job-search-card__location">India</span>
            <time datetime="2026-07-01"></time>
          </div>
        </li>
        """
        for job_id in range(start, start + count)
    )


class LinkedInProviderTests(TestCase):
    @patch("app.providers.linkedin.fetch_text")
    def test_pages_until_requested_limit(self, fetch_text) -> None:
        fetch_text.side_effect = [_cards(1000, 10), _cards(1010, 10), _cards(1020, 10)]

        jobs = fetch_linkedin_jobs(
            query="software engineer",
            location="India",
            limit=30,
            date_posted="any",
        )

        self.assertEqual(30, len(jobs))
        self.assertEqual("1000", jobs[0].external_id)
        self.assertEqual("1029", jobs[-1].external_id)
        self.assertIn("start=0", fetch_text.call_args_list[0].args[0])
        self.assertIn("start=10", fetch_text.call_args_list[1].args[0])
        self.assertIn("start=20", fetch_text.call_args_list[2].args[0])

    @patch("app.providers.linkedin.fetch_text")
    def test_stops_after_repeated_pages(self, fetch_text) -> None:
        page = _cards(2000, 10)
        fetch_text.side_effect = [page, page, page]

        jobs = fetch_linkedin_jobs(query="python", limit=100, date_posted="any")

        self.assertEqual(10, len(jobs))
        self.assertEqual(3, fetch_text.call_count)

    def test_parses_description_criteria_and_external_application(self) -> None:
        html = """
        <button><icon data-svg-class-name="apply-button__offsite-apply-icon-svg"></icon></button>
        <a class="topcard__org-name-link" href="https://in.linkedin.com/company/example?trk=jobs">Example</a>
        <div class="show-more-less-html__markup">
          Build APIs.<br><br><strong>Requirements</strong><ul><li>Python</li><li>FastAPI</li></ul>
        </div>
        <ul>
          <li class="description__job-criteria-item">
            <h3 class="description__job-criteria-subheader">Seniority level</h3>
            <span class="description__job-criteria-text description__job-criteria-text--criteria">Entry level</span>
          </li>
          <li class="description__job-criteria-item">
            <h3 class="description__job-criteria-subheader">Employment type</h3>
            <span class="description__job-criteria-text description__job-criteria-text--criteria">Full-time</span>
          </li>
        </ul>
        """

        detail = _parse_job_detail(html)

        self.assertIn("Build APIs", detail["description"])
        self.assertIn("- Python", detail["description"])
        self.assertEqual("Entry level", detail["seniority_level"])
        self.assertEqual("Full-time", detail["employment_type"])
        self.assertEqual("external", detail["application_method"])
        self.assertEqual("https://in.linkedin.com/company/example", detail["company_url"])

    def test_detects_easy_apply(self) -> None:
        detail = _parse_job_detail(
            '<button><icon data-svg-class-name="apply-button__easy-apply-icon-svg"></icon></button>'
        )

        self.assertEqual("easy_apply", detail["application_method"])

    @patch("app.providers.linkedin.time.sleep")
    @patch("app.providers.linkedin.fetch_linkedin_job_details")
    def test_retries_throttled_detail_fetch(self, fetch_details, sleep) -> None:
        job = JobCreate(source="linkedin", external_id="123", title="Engineer", company="Example")
        fetch_details.side_effect = [
            ConnectorFetchError("throttled", status_code=429, retry_after=0),
            job.model_copy(update={"description": "A" * 200, "details_status": "complete"}),
        ]

        jobs, enriched, failed = enrich_linkedin_jobs(
            [job],
            max_workers=1,
            min_interval=0,
            max_attempts=2,
        )

        self.assertEqual("complete", jobs[0].details_status)
        self.assertEqual((1, 0), (enriched, failed))
        self.assertEqual(2, fetch_details.call_count)

    @patch("app.providers.linkedin.time.sleep")
    @patch("app.providers.linkedin.fetch_linkedin_job_details")
    def test_reports_failed_detail_fetch(self, fetch_details, sleep) -> None:
        job = JobCreate(source="linkedin", external_id="123", title="Engineer", company="Example")
        fetch_details.side_effect = ConnectorFetchError("still throttled", status_code=429)

        jobs, enriched, failed = enrich_linkedin_jobs(
            [job],
            max_workers=1,
            min_interval=0,
            max_attempts=2,
        )

        self.assertEqual("failed", jobs[0].details_status)
        self.assertEqual((0, 1), (enriched, failed))
        self.assertIn("throttled", jobs[0].details_error)
