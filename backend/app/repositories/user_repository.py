"""User persistence helpers."""

from sqlalchemy.orm import Session

from app.models.user import User


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email.lower()).first()


def get_user_by_google_sub(db: Session, google_sub: str) -> User | None:
    return db.query(User).filter(User.google_sub == google_sub).first()


def create_user(db: Session, *, email: str, hashed_password: str, full_name: str | None = None) -> User:
    user = User(email=email.lower(), hashed_password=hashed_password, full_name=full_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_google_user(
    db: Session,
    *,
    email: str,
    full_name: str | None,
    google_sub: str,
    hashed_password: str,
    picture: str | None = None,
) -> User:
    user = User(
        email=email.lower(),
        full_name=full_name,
        google_sub=google_sub,
        picture=picture,
        auth_provider="google",
        hashed_password=hashed_password,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def link_google_user(
    db: Session,
    user: User,
    *,
    google_sub: str,
    full_name: str | None = None,
    picture: str | None = None,
) -> User:
    user.google_sub = google_sub
    if user.auth_provider == "password":
        user.auth_provider = "google"
    if full_name and not user.full_name:
        user.full_name = full_name
    if picture:
        user.picture = picture
    db.commit()
    db.refresh(user)
    return user
