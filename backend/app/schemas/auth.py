from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RegisterIn(StrictModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="", max_length=100)


class LoginIn(StrictModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserSettings(StrictModel):
    memory_enabled: bool = True
    learning_topic: str = Field(default="", max_length=120)


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    created_at: datetime
    settings: dict = {}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class ProfileUpdate(StrictModel):
    name: str | None = Field(default=None, max_length=100)
    settings: UserSettings | None = None


class PasswordChange(StrictModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
