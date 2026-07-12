from unittest import TestCase

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.session import Base
from app.models.job import Job
from app.models.user import User
from app.schemas.application import ApplicationPrepareRequest, ApplicationProfileUpdate, ApplicationStatusUpdate
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
