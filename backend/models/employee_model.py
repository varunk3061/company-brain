from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel, ConfigDict, EmailStr, SecretStr, Field
)

#--------------------------------------------------------------------------------------------

# Allowed employee roles
EmployeeRole = Literal["developer", "tester" , "devops" , "hr" , "finance"]

# Allowed Departments
EmployeeDepartment = Literal [
    "IT", "HR", "Finance", "Support", 
]

# Allowed Account Status
EmployeeStatus = Literal["active", "blocked"]

#--------------------------------------------------------------------------------------------

class EmployeeCreate(BaseModel):
    """Data required to create an emplyee"""

    model_config = ConfigDict(extra="forbid")

    name : str=Field(min_length=2, max_length=10)

    email : EmailStr

    password : SecretStr = Field(min_length=3, max_length=16)

#--------------------------------------------------------------------------------------------

class EmployeeUpdate(BaseModel):
    """Fields an admin can update for an eployee"""

    model_config = ConfigDict(extra="forbid")

    department : EmployeeDepartment 
    role : EmployeeRole
    status : EmployeeStatus

#--------------------------------------------------------------------------------------------

class EmployeeResponse(BaseModel):
    """Safe employee information returned by the API"""

    employee_uuid : str
    name : str
    email : EmailStr
    department : str
    role : str
    status : EmployeeStatus
    created_at : datetime
    updated_at : datetime

#--------------------------------------------------------------------------------------------

class AdminLoginRequest(BaseModel):
    """Request body for admin login."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=72)

#--------------------------------------------------------------------------------------------

class EmployeeListResponse(BaseModel):
    """Paginated employee list returned by the API"""

    items: list[EmployeeResponse]
    total: int
    page: int
    page_size: int

#--------------------------------------------------------------------------------------------

class EmployeeLoginRequest(BaseModel):
    """Request body for employee login."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=72)

#--------------------------------------------------------------------------------------------