from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr

#--------------------------------------------------------------------------------------------

UserStatus = Literal["active", "blocked"]

#--------------------------------------------------------------------------------------------

class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: SecretStr = Field(min_length=12, max_length=72)
    department_code: str
    role_code: str


class UserUpdate(BaseModel):
    """Fields an admin can change. Omitted fields stay as they are."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=100)
    department_code: str | None = None
    role_code: str | None = None
    status: UserStatus | None = None


class UserResponse(BaseModel):
    """Safe user fields returned by the API (never the hash or Mongo _id)."""

    user_uuid: str
    name: str
    email: EmailStr
    department_code: str
    department_name: str
    role_code: str
    role_name: str
    status: UserStatus
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=72)


class SessionUser(BaseModel):
    """What the UI needs to render navigation; the server still enforces every rule."""

    user_uuid: str
    name: str
    email: str
    department_code: str
    department_name: str
    role_code: str
    role_name: str
    clearance: str
    permissions: list[str]


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: SessionUser
