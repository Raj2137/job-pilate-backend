from unittest import TestCase

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.session import Base
from app.models.job import Job
from app.models.user import User
from app.repositories.tailored_resume_repository import create_tailored_resume
from app.schemas.application import ApplicationPrepareRequest, ApplicationProfileUpdate, ApplicationStatusUpdate
from app.schemas.resume import TailoredResumeResponse
from app.services.application_service import change_application_status, prepare_application, save_profile


class ApplicationServiceTests(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(
            email="raj@example.com",
            full_name="Raj Kumar",
            hashed_password="hashed",
            is_active=True,
        )
        self.job = Job(
            source="greenhouse",
            external_id="example:1",
            title="Backend Engineer",
            company="Example",
            apply_url="https://example.com/apply",
        )
        self.db.add_all([self.user, self.job])
        self.db.commit()
        self.db.refresh(self.user)
        self.db.refresh(self.job)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_prepares_complete_user_reviewed_application(self) -> None:
        save_profile(
            self.db,
            self.user,
            ApplicationProfileUpdate(
                phone="+91-9999999999",
                current_location="Bengaluru, India",
                resume_url="https://files.example.com/resume.pdf",
                work_authorization="India",
                requires_sponsorship=False,
            ),
        )

        application = prepare_application(
            self.db,
            self.user,
            ApplicationPrepareRequest(job_id=self.job.id),
        )

        self.assertEqual("ready_for_review", application.status)
        self.assertEqual([], application.missing_fields)
        self.assertEqual("raj@example.com", application.field_values["email"])

        with self.assertRaises(ValueError):
            change_application_status(
                self.db,
                self.user,
                application.id,
                ApplicationStatusUpdate(status="submitted", user_confirmed=False),
            )

        submitted = change_application_status(
            self.db,
            self.user,
            application.id,
            ApplicationStatusUpdate(status="submitted", user_confirmed=True),
        )
        self.assertEqual("submitted", submitted.status)
        self.assertTrue(submitted.user_confirmed)

    def test_reports_missing_fields_instead_of_submitting(self) -> None:
        save_profile(self.db, self.user, ApplicationProfileUpdate())

        application = prepare_application(
            self.db,
            self.user,
            ApplicationPrepareRequest(job_id=self.job.id),
        )

        self.assertEqual("draft", application.status)
        self.assertIn("phone", application.missing_fields)
        self.assertIn("resume_url", application.missing_fields)

    def test_prepares_application_with_saved_tailored_resume(self) -> None:
        save_profile(
            self.db,
            self.user,
            ApplicationProfileUpdate(
                phone="+91-9999999999",
                current_location="Bengaluru, India",
            ),
        )
        generated = TailoredResumeResponse(
            job_id=self.job.id,
            job_title=self.job.title,
            company=self.job.company,
            source_resume_id=None,
            tailored_resume_markdown="# Raj Kumar\n## Experience\n- Built Python APIs.",
            headline="Backend Engineer",
            professional_summary="Backend engineer building Python APIs.",
            core_skills=["Python"],
            keywords_incorporated=["Python"],
            unsupported_job_requirements=[],
            change_summary=[],
            truthfulness_warnings=[],
            estimated_alignment_score=80,
            provider="openai",
            model="gpt-test",
        )
        resume = create_tailored_resume(
            self.db,
            user_id=self.user.id,
            generated=generated,
            filename="example-backend-v1.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            file_data=b"docx",
            storage_provider="database",
            storage_key="users/1/resumes/example-backend-v1.docx",
        )

        application = prepare_application(
            self.db,
            self.user,
            ApplicationPrepareRequest(job_id=self.job.id, tailored_resume_id=resume.id),
        )

        self.assertEqual("ready_for_review", application.status)
        self.assertEqual(resume.id, application.field_values["tailored_resume_id"])
        self.assertEqual(resume.filename, application.field_values["resume_filename"])
        self.assertEqual(
            f"/api/resumes/tailored/{resume.id}/download",
            application.field_values["resume_url"],
        )
