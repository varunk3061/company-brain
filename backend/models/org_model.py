from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#--------------------------------------------------------------------------------------------

# Ordered least -> most sensitive; the index is the numeric level used by the access policy.
Classification = Literal["public", "internal", "confidential", "restricted"]

Permission = Literal[
    "users.manage", "org.manage", "documents.manage", "documents.approve", "audit.read", "sensitive.pii.read", "sensitive.compensation.read", "sensitive.financial.read", "sensitive.legal.read"
]

ActiveStatus = Literal["active", "inactive"]

CODE_PATTERN = r"^[A-Z][A-Z0-9_]{1,39}$"

#--------------------------------------------------------------------------------------------

class DepartmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=CODE_PATTERN)
    name: str = Field(min_length=2, max_length=100)


class DepartmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=100)
    status: ActiveStatus | None = None


class DepartmentResponse(BaseModel):
    department_uuid: str
    code: str
    name: str
    status: ActiveStatus
    created_at: datetime
    updated_at: datetime

#--------------------------------------------------------------------------------------------

class RoleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=CODE_PATTERN)
    name: str = Field(min_length=2, max_length=100)
    department_code: str
    clearance: Classification = "internal"
    permissions: list[Permission] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=100)
    clearance: Classification | None = None
    permissions: list[Permission] | None = None
    status: ActiveStatus | None = None


class RoleResponse(BaseModel):
    role_uuid: str
    code: str
    name: str
    department_code: str
    clearance: Classification
    permissions: list[str]
    status: ActiveStatus
    created_at: datetime
    updated_at: datetime
