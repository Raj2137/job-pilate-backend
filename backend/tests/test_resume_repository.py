from unittest import TestCase

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.session import Base
from app.models.resume import UserResume
from app.models.user import User
from app.repositories.resume_repository import delete_user_resume, get_user_resume, upsert_user_resume
from app.schemas.resume import UserResumeUpsert


class ResumeRepositoryTests(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(email="raj@example.com", full_name="Raj", hashed_password="hashed")
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_resume_can_be_checked_uploaded_replaced_and_deleted(self) -> None:
        self.assertIsNone(get_user_resume(self.db, self.user.id))

        created = upsert_user_resume(
            self.db,
            user_id=self.user.id,
            payload=UserResumeUpsert(
                resume_text="Full stack developer with Python, FastAPI, React, and agentic workflow experience.",
                filename="raj-resume.pdf",
                content_type="application/pdf",
            ),
        )

        self.assertEqual("raj-resume.pdf", created.filename)
        self.assertEqual(created.character_count, len(created.resume_text))

        replaced = upsert_user_resume(
            self.db,
            user_id=self.user.id,
            payload=UserResumeUpsert(
                resume_text="Backend engineer with Python, FastAPI, PostgreSQL, Docker, and cloud APIs.",
                filename="raj-resume-v2.txt",
                content_type="text/plain",
            ),
        )

        self.assertEqual(created.id, replaced.id)
        self.assertEqual("raj-resume-v2.txt", replaced.filename)
        self.assertEqual(1, self.db.query(UserResume).filter(UserResume.user_id == self.user.id).count())
        self.assertTrue(delete_user_resume(self.db, user_id=self.user.id))
        self.assertFalse(delete_user_resume(self.db, user_id=self.user.id))
        self.assertIsNone(get_user_resume(self.db, self.user.id))
