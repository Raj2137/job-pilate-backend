"""User response schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserRead(BaseModel):
    id: int
    email: EmailStr
    full_name: str | None
    auth_provider: str
    picture: str | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
