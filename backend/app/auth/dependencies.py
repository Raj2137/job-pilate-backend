"""Authentication dependencies."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import ALGORITHM
from app.database.session import get_db
from app.models.user import User
from app.repositories.user_repository import get_user_by_email

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = credentials.credentials
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not isinstance(email, str):
            raise credentials_error
    except JWTError as exc:
        raise credentials_error from exc

    user = get_user_by_email(db, email)
    if user is None or not user.is_active:
        raise credentials_error
    return user
