"""Auth request and response schemas."""

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.schemas.user import UserRead


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class GoogleLogin(BaseModel):
    id_token: str | None = Field(default=None, min_length=20)
    credential: str | None = Field(default=None, min_length=20)

    @model_validator(mode="after")
    def require_google_token(self) -> "GoogleLogin":
        if not self.id_token and not self.credential:
            raise ValueError("id_token or credential is required")
        return self

    @property
    def token(self) -> str:
        return self.id_token or self.credential or ""


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthSession(Token):
    user: UserRead
