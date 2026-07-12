from unittest import TestCase
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.session import Base
from app.models.user import User
from app.services.google_auth_service import GoogleIdentity, sign_in_with_google


class GoogleAuthTests(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    @patch("app.services.google_auth_service.verify_google_id_token")
    def test_google_signin_creates_user_and_returns_token(self, verify_google_id_token) -> None:
        verify_google_id_token.return_value = GoogleIdentity(
            sub="google-sub-1",
            email="raj@example.com",
            full_name="Raj Kumar",
            email_verified=True,
        )

        token = sign_in_with_google(self.db, "google-id-token")

        user = self.db.query(User).filter(User.email == "raj@example.com").first()
        self.assertIsNotNone(user)
        self.assertEqual("google-sub-1", user.google_sub)
        self.assertEqual("google", user.auth_provider)
        self.assertTrue(token.access_token)

    @patch("app.services.google_auth_service.verify_google_id_token")
    def test_google_signin_links_existing_email_user(self, verify_google_id_token) -> None:
        existing = User(
            email="raj@example.com",
            full_name=None,
            hashed_password="hashed",
            auth_provider="password",
        )
        self.db.add(existing)
        self.db.commit()
        verify_google_id_token.return_value = GoogleIdentity(
            sub="google-sub-2",
            email="raj@example.com",
            full_name="Raj Kumar",
            email_verified=True,
        )

        sign_in_with_google(self.db, "google-id-token")

        self.db.refresh(existing)
        self.assertEqual("google-sub-2", existing.google_sub)
        self.assertEqual("google", existing.auth_provider)
        self.assertEqual("Raj Kumar", existing.full_name)
