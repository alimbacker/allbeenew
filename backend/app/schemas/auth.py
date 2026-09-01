"""Auth request/response models."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Imported from our wrapper so private-network domains (.local) are accepted.
from app.schemas.email import EmailStr

PASSWORD_MIN = 8
PASSWORD_MAX = 72  # bcrypt's hard limit


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120, examples=["Mohamed Rafi"])
    email: EmailStr = Field(..., examples=["photographer@example.com"])
    password: str = Field(..., min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)
    confirm_password: str = Field(..., min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be blank")
        return v

    @field_validator("password")
    @classmethod
    def _strength(cls, v: str) -> str:
        if v.isdigit() or v.isalpha():
            raise ValueError("Use a mix of letters and numbers")
        return v

    @model_validator(mode="after")
    def _match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=PASSWORD_MAX)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: EmailStr
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token lifetime in seconds")
    user: UserOut
