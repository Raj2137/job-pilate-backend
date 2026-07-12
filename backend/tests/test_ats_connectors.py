from unittest import TestCase
from unittest.mock import patch

from app.providers.ashby import fetch_ashby_jobs
from app.providers.ats_detection import detect_ats
from app.providers.company_index import COMPANY_SEEDS
from app.providers.generic_career import _jobs_from_html
from app.providers.smartrecruiters import fetch_smartrecruiters_jobs
from app.providers.workday import fetch_workday_jobs


class ATSConnectorTests(TestCase):
    def test_launch_registry_has_50_unique_companies(self) -> None:
        self.assertEqual(50, len(COMPANY_SEEDS))
        self.assertEqual(50, len({company.name for company in COMPANY_SEEDS}))
        self.assertTrue(all(company.industry for company in COMPANY_SEEDS))

    def test_detects_supported_ats_urls(self) -> None:
        cases = {
            "https://job-boards.greenhouse.io/stripe": ("greenhouse", "stripe"),
            "https://jobs.lever.co/razorpay": ("lever", "razorpay"),
            "https://jobs.ashbyhq.com/notion": ("ashby", "notion"),
            "https://careers.smartrecruiters.com/Visa": ("smartrecruiters", "Visa"),
            "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite": (
                "workday",
                "nvidia|NVIDIAExternalCareerSite",
            ),
        }
        for url, expected in cases.items():
            detected = detect_ats(url)
            self.assertEqual(expected, (detected.ats_type, detected.identifier))

    @patch("app.providers.ashby.fetch_json")
    def test_normalizes_ashby_job(self, fetch_json) -> None:
        fetch_json.return_value = {
            "jobs": [
                {
                    "id": "abc",
                    "title": "Backend Engineer",
                    "location": "Remote",
                    "descriptionHtml": "<p>Build reliable APIs and distributed systems.</p>" * 5,
                    "jobUrl": "https://jobs.ashbyhq.com/example/abc",
                    "applyUrl": "https://jobs.ashbyhq.com/example/abc/application",
                    "publishedAt": "2026-07-01T12:00:00Z",
                    "isRemote": True,
                    "employmentType": "Full-time",
                }
            ]
        }

        jobs = fetch_ashby_jobs("example", company_name="Example")

        self.assertEqual(1, len(jobs))
        self.assertEqual("Example", jobs[0].company)
        self.assertEqual("complete", jobs[0].details_status)
        self.assertTrue(jobs[0].remote)

    @patch("app.providers.smartrecruiters.fetch_json")
    def test_normalizes_smartrecruiters_detail(self, fetch_json) -> None:
        summary = {
            "id": "123",
            "name": "Platform Engineer",
            "releasedDate": "2026-07-01T12:00:00Z",
            "location": {"fullLocation": "Bengaluru, India", "remote": False},
        }
        detail = {
            **summary,
            "postingUrl": "https://jobs.smartrecruiters.com/Example/123-platform-engineer",
            "applyUrl": "https://jobs.smartrecruiters.com/Example/123-platform-engineer?oga=true",
            "company": {"name": "Example"},
            "jobAd": {
                "sections": {
                    "jobDescription": {"title": "Job Description", "text": "<p>Build platforms.</p>" * 20},
                    "qualifications": {"title": "Qualifications", "text": "<p>Python and SQL.</p>" * 10},
                }
            },
            "typeOfEmployment": {"label": "Full-time"},
            "experienceLevel": {"label": "Mid-Senior Level"},
        }
        fetch_json.side_effect = [
            {"content": [summary], "totalFound": 1},
            detail,
        ]

        jobs = fetch_smartrecruiters_jobs("Example", max_jobs=10, max_workers=1)

        self.assertEqual(1, len(jobs))
        self.assertEqual("complete", jobs[0].details_status)
        self.assertEqual("Mid-Senior Level", jobs[0].seniority_level)

    @patch("app.providers.workday.fetch_json")
    @patch("app.providers.workday.post_json")
    def test_normalizes_workday_detail(self, post_json, fetch_json) -> None:
        post_json.return_value = {
            "jobPostings": [
                {
                    "title": "Software Engineer",
                    "externalPath": "/job/India/Software-Engineer_JR1",
                    "locationsText": "India",
                }
            ]
        }
        fetch_json.return_value = {
            "jobPostingInfo": {
                "title": "Software Engineer",
                "jobReqId": "JR1",
                "jobDescription": "<p>Build distributed systems.</p>" * 20,
                "location": "India",
                "startDate": "2026-07-01",
                "timeType": "Full time",
            }
        }

        jobs = fetch_workday_jobs(
            "https://example.wd5.myworkdayjobs.com/External",
            company_name="Example",
            max_jobs=10,
            max_workers=1,
        )

        self.assertEqual(1, len(jobs))
        self.assertEqual("Example", jobs[0].company)
        self.assertEqual("complete", jobs[0].details_status)

    def test_parses_schema_org_job_posting(self) -> None:
        html = """
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "JobPosting",
          "identifier": {"value": "JOB-1"},
          "title": "API Engineer",
          "description": "<p>Build APIs and services.</p><p>Python FastAPI PostgreSQL</p>",
          "datePosted": "2026-07-01",
          "employmentType": "FULL_TIME",
          "hiringOrganization": {"name": "Example"},
          "jobLocation": {"address": {"addressLocality": "Pune", "addressCountry": "India"}},
          "url": "https://careers.example.com/jobs/1"
        }
        </script>
        """

        jobs = _jobs_from_html(html, base_url="https://careers.example.com/jobs", company_name="Example")

        self.assertEqual(1, len(jobs))
        self.assertEqual("JOB-1", jobs[0].external_id)
        self.assertEqual("Pune, India", jobs[0].location)
