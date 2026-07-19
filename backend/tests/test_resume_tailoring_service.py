import json
from unittest import TestCase
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.session import Base
from app.models.job import Job
from app.models.user import User
from app.repositories.llm_key_repository import create_llm_key
from app.repositories.resume_repository import upsert_user_resume
from app.schemas.llm_key import LlmKeyCreate, LlmProvider
from app.schemas.resume import TailoredResumeRequest, UserResumeUpsert
from app.services.resume_tailoring_service import (
    ResumeTailoringProviderError,
    tailor_resume_for_job,
)


class ResumeTailoringServiceTests(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(email="raj@example.com", full_name="Raj", hashed_password="hashed")
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)
        self.resume = upsert_user_resume(
            self.db,
            user_id=self.user.id,
            payload=UserResumeUpsert(
                resume_text=(
                    "Raj Kumar\nBackend Engineer\n"
                    "Built Python and FastAPI services backed by PostgreSQL. "
                    "Created REST APIs and Docker-based deployments at Acme from 2024 to Present."
                ),
                filename="resume.txt",
                content_type="text/plain",
            ),
        )
        self.job = Job(
            source="greenhouse",
            external_id="tailor-job-1",
            title="Backend Engineer",
            company="Example Co",
            location="India",
            description=(
                "Build Python microservices with FastAPI, PostgreSQL, Kubernetes, and AWS. "
                "Requires three years of backend engineering experience."
            ),
            remote=True,
            details_status="complete",
        )
        self.db.add(self.job)
        self.db.commit()
        self.db.refresh(self.job)
        self.key = create_llm_key(
            self.db,
            self.user,
            LlmKeyCreate(provider=LlmProvider.OPENAI, api_key="sk-test-1234567890"),
        )

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    @patch("app.services.resume_tailoring_service.complete_text")
    def test_tailors_resume_without_adding_unsupported_requirements(self, complete_text) -> None:
        analysis = {
            "candidate_positioning": "Backend engineer focused on Python API services.",
            "candidate_keywords": ["Python", "FastAPI", "PostgreSQL", "REST APIs", "Docker"],
            "candidate_evidence": [
                {
                    "claim": "Builds Python API services",
                    "source_evidence": "Built Python and FastAPI services backed by PostgreSQL.",
                }
            ],
            "required_job_keywords": ["Python", "FastAPI", "PostgreSQL", "Kubernetes", "AWS"],
            "preferred_job_keywords": [],
            "matched_keywords": ["Python", "FastAPI", "PostgreSQL"],
            "missing_keywords": ["Kubernetes", "AWS", "3 years of experience"],
            "transferable_strengths": ["Docker-based deployment experience"],
            "seniority_alignment": "The source shows experience since 2024; the three-year requirement is unsupported.",
            "resume_strategy": ["Lead with Python API and database experience."],
            "truthfulness_risks": ["Do not claim Kubernetes, AWS, or three years of experience."],
        }
        tailored = (
            {
                "tailored_resume_markdown": (
                    "# Raj Kumar\n## Backend Engineer\n\n"
                    "### Summary\nBackend engineer building Python and FastAPI services.\n\n"
                    "### Skills\nPython, FastAPI, PostgreSQL, REST APIs, Docker\n\n"
                    "### Experience\n- Built Python and FastAPI services backed by PostgreSQL.\n"
                    "- Created REST APIs and Docker-based deployments."
                ),
                "headline": "Backend Engineer | Python, FastAPI, PostgreSQL",
                "professional_summary": "Backend engineer building Python and FastAPI services.",
                "core_skills": ["Python", "FastAPI", "PostgreSQL", "REST APIs", "Docker"],
                "keywords_incorporated": ["Python", "FastAPI", "PostgreSQL"],
                "unsupported_job_requirements": ["Kubernetes", "AWS", "3 years of experience"],
                "change_summary": ["Prioritized backend API experience."],
                "truthfulness_warnings": ["Candidate should verify exact employment date formatting."],
                "estimated_alignment_score": 72,
            }
        )
        complete_text.side_effect = [json.dumps(analysis), json.dumps(tailored)]

        result = tailor_resume_for_job(
            self.db,
            user=self.user,
            payload=TailoredResumeRequest(job_id=self.job.id, llm_key_id=self.key.id),
        )

        self.assertEqual(self.job.id, result.job_id)
        self.assertEqual(self.resume.id, result.source_resume_id)
        self.assertEqual(72, result.estimated_alignment_score)
        self.assertIn("Kubernetes", result.unsupported_job_requirements)
        self.assertNotIn("Kubernetes", result.tailored_resume_markdown)
        self.assertEqual(2, complete_text.call_count)
        analysis_request = complete_text.call_args_list[0].args[0]
        writer_request = complete_text.call_args_list[1].args[0]
        self.assertIn("never invent", analysis_request.system_prompt)
        self.assertIn(self.job.description, analysis_request.user_prompt)
        self.assertIn("verified_alignment_context", writer_request.user_prompt)

    @patch("app.services.resume_tailoring_service.complete_text")
    def test_rejects_invalid_ai_resume_output(self, complete_text) -> None:
        complete_text.return_value = '{"candidate_positioning":"Backend Engineer"}'

        with self.assertRaises(ResumeTailoringProviderError):
            tailor_resume_for_job(
                self.db,
                user=self.user,
                payload=TailoredResumeRequest(job_id=self.job.id, llm_key_id=self.key.id),
            )

    @patch("app.services.resume_tailoring_service.complete_text")
    def test_accepts_frontend_resume_and_automatically_selects_active_key(self, complete_text) -> None:
        analysis = {
            "candidate_positioning": "Backend engineer focused on Python services.",
            "candidate_keywords": ["Python", "FastAPI"],
            "candidate_evidence": [{"claim": "Python services", "source_evidence": "Built Python services."}],
            "required_job_keywords": ["Python"],
            "preferred_job_keywords": [],
            "matched_keywords": ["Python"],
            "missing_keywords": ["Kubernetes"],
            "transferable_strengths": [],
            "seniority_alignment": "Partial match.",
            "resume_strategy": ["Prioritize Python work."],
            "truthfulness_risks": [],
        }
        tailored = {
            "tailored_resume_markdown": "# Raj Kumar\n\nBackend Engineer with Python experience.",
            "headline": "Backend Engineer",
            "professional_summary": "Backend engineer with Python experience.",
            "core_skills": ["Python"],
            "keywords_incorporated": ["Python"],
            "unsupported_job_requirements": ["Kubernetes"],
            "change_summary": ["Prioritized Python experience."],
            "truthfulness_warnings": [],
            "estimated_alignment_score": 60,
        }
        complete_text.side_effect = [json.dumps(analysis), json.dumps(tailored)]

        result = tailor_resume_for_job(
            self.db,
            user=self.user,
            payload=TailoredResumeRequest(
                job_id=self.job.id,
                resume_text="Raj Kumar. Backend engineer who built Python services and REST APIs.",
            ),
        )

        self.assertIsNone(result.source_resume_id)
        self.assertEqual(self.key.id, self.db.query(type(self.key)).one().id)
        self.assertEqual("openai", result.provider)
