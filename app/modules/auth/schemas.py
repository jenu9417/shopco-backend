import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.auth.models import Role


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, pattern=r"^\+?[0-9]{10,15}$", examples=["+919876543210"])

    @field_validator("email")
    @classmethod
    def _lower_email(cls, v: str) -> str:
        return str(v).strip().lower()

    @field_validator("password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one letter and one digit")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)

    @field_validator("email")
    @classmethod
    def _lower_email(cls, v: str) -> str:
        return str(v).strip().lower()


class UpdateProfileRequest(BaseModel):
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, pattern=r"^\+?[0-9]{10,15}$")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    first_name: str | None
    last_name: str | None
    phone: str | None
    role: Role
    created_at: datetime


class AuthResponse(BaseModel):
    """The refresh token is NOT in the body - it is set as an httpOnly cookie."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")
    user: UserOut
