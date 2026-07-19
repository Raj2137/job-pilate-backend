from unittest import TestCase
from unittest.mock import patch
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ai.job_matcher import match_jobs_for_resume
from app.database.session import Base
from app.models.job import Job
from app.models.user import User
from app.repositories.llm_key_repository import create_llm_key
from app.repositories.job_repository import list_job_filter_options
from app.schemas.job import ResumeJobMatchRequest
from app.schemas.llm_key import LlmKeyCreate, LlmProvider


class JobFiltersAndMatchTests(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add_all(
            [
                Job(
                    source="linkedin",
                    external_id="backend-1",
                    title="Backend Engineer",
                    company="Stripe",
                    location="Bengaluru, India",
                    description="Build Python FastAPI services with PostgreSQL, Redis, and cloud APIs.",
                    remote=True,
                    employment_type="full-time",
                    application_method="external",
                    details_status="complete",
                    posted_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=2),
                ),
                Job(
                    source="greenhouse",
                    external_id="design-1",
                    title="Product Designer",
                    company="Figma",
                    location="San Francisco, CA",
                    description="Design workflows and collaborate with product teams.",
                    remote=False,
                    employment_type="full-time",
                    application_method="external",
                    details_status="complete",
                    posted_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=20),
                ),
                Job(
                    source="linkedin",
                    external_id="missing-jd-1",
                    title="Frontend Engineer",
                    company="Notion",
                    location="India",
                    description=None,
                    remote=True,
                    details_status="pending",
                    posted_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1),
                ),
                Job(
                    source="linkedin",
                    external_id="senior-1",
                    title="Senior Frontend Engineer",
                    company="GoCharting",
                    location="Chennai, India",
                    description=(
                        "Senior hands-on frontend engineer with React, TypeScript, WebSocket APIs, "
                        "backend collaboration, real-time platform work, and 7-10 years frontend engineering experience."
                    ),
                    remote=False,
                    seniority_level="Mid-Senior level",
                    details_status="complete",
                    posted_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1),
                ),
                Job(
                    source="workday",
                    external_id="architect-1",
                    title="Technical Architect (Cloud & Platform Engineering)",
                    company="Bosch",
                    location="Hyderabad, India",
                    description=(
                        "Architect cloud platform engineering roadmaps, technical governance, stakeholder alignment, "
                        "and distributed enterprise systems for senior platform teams."
                    ),
                    remote=False,
                    seniority_level="Senior level",
                    details_status="complete",
                    posted_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1),
                ),
                Job(
                    source="greenhouse",
                    external_id="manager-1",
                    title="Engineering Manager, Agent Runtime Platform",
                    company="Anthropic",
                    location="San Francisco, CA",
                    description=(
                        "Manage engineering teams building agent runtime platforms. Requires leadership, strategy, "
                        "execution ownership, and 8+ years of software engineering experience."
                    ),
                    remote=False,
                    seniority_level="Manager",
                    details_status="complete",
                    posted_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1),
                ),
            ]
        )
        self.user = User(email="raj@example.com", full_name="Raj", hashed_password="hashed")
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_filter_options_include_counts_and_jd_coverage(self) -> None:
        filters = list_job_filter_options(self.db)

        self.assertEqual(6, filters["total_jobs"])
        self.assertEqual(5, filters["jobs_with_jd"])
        self.assertEqual(1, filters["jobs_without_jd"])
        self.assertIn({"value": "linkedin", "count": 3}, filters["sources"])
        self.assertIn({"value": "true", "count": 2}, filters["remote"])

    def test_resume_match_ranks_relevant_jobs(self) -> None:
        response = match_jobs_for_resume(
            self.db,
            ResumeJobMatchRequest(
                resume_text=(
                    "Backend engineer with 4 years of experience building Python FastAPI APIs, "
                    "PostgreSQL data models, Redis queues, and cloud services."
                ),
                job_title="backend engineer",
                target_roles=["backend engineer"],
                skills=["Python", "FastAPI", "PostgreSQL", "Redis"],
                preferred_locations=["India"],
                years_experience=4,
                remote=True,
                posted_within_days=7,
                limit=5,
            ),
        )

        self.assertGreaterEqual(response.total_candidates, 1)
        self.assertEqual("Backend Engineer", response.items[0].job.title)
        self.assertGreater(response.items[0].score, 50)
        self.assertIn("python", response.items[0].matched_keywords)

    def test_resume_only_match_infers_role_and_experience(self) -> None:
        response = match_jobs_for_resume(
            self.db,
            ResumeJobMatchRequest(
                resume_text=(
                    "Associate Full Stack Developer at Techolution July 2024 - Present. "
                    "Built Email-to-Jira automation agents, a VS Code extension, repository analyser UI, "
                    "and deployment automation. Skills: Python, JavaScript, TypeScript, React.js, Angular, "
                    "FastAPI, Node.js, Express.js, REST APIs, WebSockets, MongoDB, SQL Server, GCP Cloud Build, "
                    "AWS basics, Docker, OpenAI API, LLM integration, agentic workflows."
                ),
                limit=10,
                require_jd=True,
            ),
        )

        titles = [item.job.title for item in response.items]
        self.assertIn("full stack developer", response.inferred_target_roles)
        self.assertEqual(2, response.inferred_years_experience)
        self.assertEqual("Backend Engineer", response.items[0].job.title)
        backend = next(item for item in response.items if item.job.title == "Backend Engineer")
        if "Technical Architect (Cloud & Platform Engineering)" in titles:
            architect = next(item for item in response.items if item.job.title.startswith("Technical Architect"))
            self.assertLess(architect.score, backend.score)
        if "Engineering Manager, Agent Runtime Platform" in titles:
            manager = next(item for item in response.items if item.job.title.startswith("Engineering Manager"))
            self.assertLess(manager.score, backend.score)
        self.assertGreater(response.items[0].score, 50)
        self.assertIn("python", response.items[0].matched_keywords)

    def test_resume_match_penalizes_roles_that_are_too_senior(self) -> None:
        response = match_jobs_for_resume(
            self.db,
            ResumeJobMatchRequest(
                resume_text="Full stack developer with 2 years Python FastAPI React TypeScript API experience.",
                job_title="full stack developer",
                target_roles=["frontend engineer", "backend engineer"],
                skills=["React", "TypeScript", "FastAPI"],
                preferred_locations=["India"],
                years_experience=2,
                posted_within_days=7,
                limit=10,
            ),
        )

        titles = [item.job.title for item in response.items]
        self.assertIn("Senior Frontend Engineer", titles)
        senior = next(item for item in response.items if item.job.title == "Senior Frontend Engineer")
        backend = next(item for item in response.items if item.job.title == "Backend Engineer")
        self.assertLess(senior.score, backend.score)
        self.assertIn("too senior", senior.experience_signal)

    def test_resume_match_supports_ranked_pagination(self) -> None:
        base_payload = {
            "resume_text": "Software engineer with Python, JavaScript, React, FastAPI, APIs, and cloud experience.",
            "target_roles": ["software engineer", "backend engineer", "frontend engineer"],
            "skills": ["Python", "JavaScript", "React", "FastAPI"],
            "years_experience": 3,
            "candidate_limit": 20,
            "limit": 2,
        }

        first_page = match_jobs_for_resume(self.db, ResumeJobMatchRequest(**base_payload, page=1))
        second_page = match_jobs_for_resume(self.db, ResumeJobMatchRequest(**base_payload, page=2))

        self.assertEqual(1, first_page.page)
        self.assertEqual(2, first_page.limit)
        self.assertEqual(20, first_page.candidate_limit)
        self.assertEqual(2, first_page.returned)
        self.assertGreaterEqual(first_page.total_pages, 2)
        self.assertTrue(first_page.has_next_page)
        self.assertFalse(first_page.has_previous_page)
        self.assertEqual(2, second_page.page)
        self.assertTrue(second_page.has_previous_page)
        first_ids = {item.job.id for item in first_page.items}
        second_ids = {item.job.id for item in second_page.items}
        self.assertTrue(first_ids.isdisjoint(second_ids))

    def test_resume_match_filters_by_company(self) -> None:
        response = match_jobs_for_resume(
            self.db,
            ResumeJobMatchRequest(
                resume_text="Software engineer with Python, APIs, JavaScript, and cloud experience.",
                target_roles=["software engineer", "backend engineer"],
                companies=["Stripe"],
                candidate_limit=20,
                limit=10,
            ),
        )

        self.assertGreaterEqual(response.returned, 1)
        self.assertTrue(all(item.job.company == "Stripe" for item in response.items))

    def test_resume_match_relaxes_filters_when_strict_preferences_find_nothing(self) -> None:
        response = match_jobs_for_resume(
            self.db,
            ResumeJobMatchRequest(
                resume_text=(
                    "Full stack developer with Python, FastAPI, React, TypeScript, PostgreSQL, "
                    "MongoDB, cloud deployment, and AI agent experience."
                ),
                job_title="full stack developer",
                target_roles=["backend engineer", "software engineer", "ai engineer"],
                skills=["Python", "FastAPI", "React", "TypeScript"],
                preferred_locations=["Hyderabad"],
                years_experience=2,
                remote=True,
                posted_within_days=1,
                limit=5,
            ),
        )

        self.assertTrue(response.relaxed)
        self.assertGreaterEqual(response.total_candidates, 1)
        self.assertIn("strict preferences: 0 candidates", response.filter_trace)
        self.assertEqual("Backend Engineer", response.items[0].job.title)

    @patch("app.ai.job_matcher.complete_text")
    def test_resume_match_can_use_user_llm_key_to_rerank(self, complete_text) -> None:
        key = create_llm_key(
            self.db,
            self.user,
            LlmKeyCreate(provider=LlmProvider.GROQ, api_key="gsk_test_1234567890"),
        )
        complete_text.return_value = """
        {
          "candidate_keywords": ["Product design", "Workflow design", "Cross-functional collaboration"],
          "items": [{
            "job_id": 2,
            "score": 91,
            "job_keywords": ["Product design", "Workflow design", "Figma"],
            "required_keywords": ["Product design", "Workflow design"],
            "preferred_keywords": ["Figma"],
            "matched_keywords": ["Product design", "Workflow design"],
            "missing_keywords": ["Figma"],
            "experience_signal": "Candidate experience aligns with the role level.",
            "reasons": ["Strong product and workflow design evidence"],
            "red_flags": []
          }]
        }
        """

        response = match_jobs_for_resume(
            self.db,
            ResumeJobMatchRequest(
                resume_text="Designer with product workflows and collaboration experience.",
                job_title="product designer",
                target_roles=["product designer"],
                years_experience=2,
                use_llm=True,
                llm_key_id=key.id,
                llm_top_k=3,
                limit=3,
            ),
            self.user,
        )

        self.assertTrue(response.llm_used)
        self.assertEqual("ai", response.evaluation_method)
        self.assertEqual("AI evaluated 1 candidate jobs.", response.llm_status)
        self.assertEqual("Product design", response.resume_keywords[0])
        self.assertEqual("Product Designer", response.items[0].job.title)
        self.assertEqual(91, response.items[0].score)
        self.assertEqual(["Product design", "Workflow design"], response.items[0].matched_keywords)
        self.assertEqual(["Figma"], response.items[0].missing_keywords)
        self.assertEqual(["Product design", "Workflow design"], response.items[0].required_keywords)
        request = complete_text.call_args.args[0]
        self.assertEqual(300, request.request_timeout_seconds)

    @patch("app.ai.job_matcher.complete_text")
    def test_ai_match_falls_back_when_structured_output_is_invalid(self, complete_text) -> None:
        key = create_llm_key(
            self.db,
            self.user,
            LlmKeyCreate(provider=LlmProvider.GROQ, api_key="gsk_test_1234567890"),
        )
        complete_text.return_value = '{"candidate_keywords":["Python"],"items":[]}'

        response = match_jobs_for_resume(
            self.db,
            ResumeJobMatchRequest(
                resume_text="Backend engineer with Python and FastAPI API development experience.",
                target_roles=["backend engineer"],
                use_llm=True,
                llm_key_id=key.id,
                limit=3,
            ),
            self.user,
        )

        self.assertFalse(response.llm_used)
        self.assertEqual("deterministic", response.evaluation_method)
        self.assertIn("AI fallback:", response.llm_status)
        self.assertGreaterEqual(response.returned, 1)
