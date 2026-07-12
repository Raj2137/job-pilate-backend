"""Authentication routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.database.session import get_db
from app.repositories.user_repository import create_user, get_user_by_email
from app.schemas.auth import AuthSession, GoogleLogin, Token, UserCreate, UserLogin
from app.schemas.user import UserRead
from app.services.google_auth_service import sign_in_with_google

router = APIRouter()


@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def signup(payload: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    if get_user_by_email(db, payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    return create_user(
        db,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )


@router.post("/signin", response_model=Token)
def signin(payload: UserLogin, db: Session = Depends(get_db)) -> Token:
    user = get_user_by_email(db, payload.email)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    return Token(access_token=create_access_token(user.email))


@router.post("/google", response_model=AuthSession)
def google_signin(payload: GoogleLogin, db: Session = Depends(get_db)) -> AuthSession:
    return sign_in_with_google(db, payload.token)
