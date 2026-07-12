from unittest import TestCase

from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth.routes import signin, signup
from app.core.security import ALGORITHM
from app.database.session import Base
from app.schemas.auth import UserCreate, UserLogin


class PasswordAuthRouteTests(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_signup_returns_token_and_user(self) -> None:
        session = signup(
            UserCreate(email="Raj@Example.com", password="testing@123", full_name="Raj Kumar"),
            self.db,
        )

        self.assertTrue(session.access_token)
        self.assertEqual("bearer", session.token_type)
        self.assertEqual("raj@example.com", session.user.email)
        self.assertEqual("Raj Kumar", session.user.full_name)

        claims = jwt.decode(session.access_token, "change-this-secret-in-production", algorithms=[ALGORITHM])
        self.assertEqual("raj@example.com", claims["sub"])

    def test_signin_returns_token_and_user(self) -> None:
        signup(
            UserCreate(email="raj@example.com", password="testing@123", full_name="Raj Kumar"),
            self.db,
        )

        session = signin(UserLogin(email="raj@example.com", password="testing@123"), self.db)

        self.assertTrue(session.access_token)
        self.assertEqual("bearer", session.token_type)
        self.assertEqual("raj@example.com", session.user.email)
        self.assertEqual("Raj Kumar", session.user.full_name)

        claims = jwt.decode(session.access_token, "change-this-secret-in-production", algorithms=[ALGORITHM])
        self.assertEqual("raj@example.com", claims["sub"])
