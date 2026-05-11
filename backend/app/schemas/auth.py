"""Authentication request and response payload schemas."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class _EmailMixin(BaseModel):
    @field_validator("email", check_fields=False)
    @classmethod
    def _email_shape(cls, v: str) -> str:
        if not _EMAIL_RE.match(v):
            raise ValueError("invalid email address")
        return v.lower()


class RegisterRequest(_EmailMixin):
    email: str
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(_EmailMixin):
    email: str
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    user: UserOut
