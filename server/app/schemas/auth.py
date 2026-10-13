from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["admin", "engineer", "viewer"]
USERNAME_PATTERN = r"^[A-Za-z0-9_.-]{3,64}$"


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    token: str
    tokenType: Literal["bearer"] = "bearer"
    expiresIn: int
    username: str
    displayName: str
    role: Role


class UserOut(BaseModel):
    id: int
    username: str
    displayName: str
    email: str | None
    role: Role
    isActive: bool
    lastLoginAt: datetime | None
    createdAt: datetime


class UserCreate(BaseModel):
    username: str = Field(pattern=USERNAME_PATTERN)
    displayName: str = Field(min_length=1, max_length=128)
    email: str | None = Field(default=None, max_length=256)
    role: Role
    password: str = Field(max_length=256)


class UserUpdate(BaseModel):
    displayName: str | None = Field(default=None, min_length=1, max_length=128)
    email: str | None = Field(default=None, max_length=256)
    role: Role | None = None
    isActive: bool | None = None


class PasswordReset(BaseModel):
    newPassword: str = Field(max_length=256)


class PasswordChange(BaseModel):
    currentPassword: str = Field(max_length=256)
    newPassword: str = Field(max_length=256)
