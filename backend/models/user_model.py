from typing import Literal
from pydantic import BaseModel, EmailStr, Field, field_validator

class UserCreate(BaseModel):
    name: str = Field(min_length=3, max_length=10)
    email: EmailStr
    password: str = Field(min_length=3, max_length=14)
    department: str = Field(default="IT", max_length=20)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value:str) -> str:
        value = value.strip().lower()

        if "@" not in value or "." not in value.rsplit("@",1)[-1]:
            raise ValueError("Enter a valid email address")

        return value

class UserResponse(BaseModel):
    user_uuid:str
    name:str
    email:str
    role: Literal["admin" , "employee"]
    department:str
    is_active: bool

class AdminLogin(BaseModel):
    email: str
    password: str
