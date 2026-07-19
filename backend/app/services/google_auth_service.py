"""Google ID token verification for social sign-in."""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.repositories.user_repository import (
    create_google_user,
    get_user_by_email,
    get_user_by_google_sub,
    link_google_user,
)
from app.schemas.auth import AuthSession
from app.schemas.user import UserRead


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    full_name: str | None
    email_verified: bool
    picture: str | None = None


def sign_in_with_google(db: Session, id_token: str) -> AuthSession:
    identity = verify_google_id_token(id_token)
    user = get_user_by_google_sub(db, identity.sub)
    if user is None:
        user = get_user_by_email(db, identity.email)
        if user is not None:
            user = link_google_user(
                db,
                user,
                google_sub=identity.sub,
                full_name=identity.full_name,
                picture=identity.picture,
            )
        else:
            user = create_google_user(
                db,
                email=identity.email,
                full_name=identity.full_name,
                google_sub=identity.sub,
                picture=identity.picture,
                hashed_password=hash_password(secrets.token_urlsafe(32)),
            )
    return AuthSession(access_token=create_access_token(user.email), user=UserRead.model_validate(user))


def verify_google_id_token(id_token: str) -> GoogleIdentity:
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google sign-in is not configured",
        )
    try:
        from google.auth.transport import requests
        from google.oauth2 import id_token as google_id_token
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google auth dependency is not installed",
        ) from exc

    try:
        payload = google_id_token.verify_oauth2_token(
            id_token,
            requests.Request(),
            settings.google_client_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google ID token",
        ) from exc

    sub = payload.get("sub")
    email = payload.get("email")
    email_verified = payload.get("email_verified") is True
    if not isinstance(sub, str) or not isinstance(email, str) or not email_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account email is not verified",
        )

    return GoogleIdentity(
        sub=sub,
        email=email.lower(),
        full_name=payload.get("name") if isinstance(payload.get("name"), str) else None,
        picture=payload.get("picture") if isinstance(payload.get("picture"), str) else None,
        email_verified=email_verified,
    )
