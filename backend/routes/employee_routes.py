from fastapi import APIRouter, Depends, HTTPException, status

from database.connection import employees_collection
from models.employee_model import (
    EmployeeLoginRequest,
    EmployeeResponse,
)
from utils.auth import (
    create_employee_access_token,
    get_current_employee,
)
from utils.security import verify_password


router = APIRouter(
    prefix="/employee",
    tags=["Employee"],
)


@router.post("/login")
def employee_login(login_data: EmployeeLoginRequest):
    """Authenticate an employee and return a JWT."""

    email = str(login_data.email).strip().lower()
    password = login_data.password.get_secret_value()

    employee = employees_collection.find_one({
        "email": email,
    })

    if not employee or not verify_password(
        password,
        employee["password_hash"],
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if employee.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your employee account is blocked",
        )

    token = create_employee_access_token(employee)

    return {
        "access_token": token,
        "token_type": "bearer",
    }


@router.get(
    "/me",
    response_model=EmployeeResponse,
)
def get_my_profile(
    employee: dict = Depends(get_current_employee),
):
    """Return the currently logged-in employee's profile."""

    return {
        "employee_uuid": employee["employee_uuid"],
        "name": employee["name"],
        "email": employee["email"],
        "department": employee["department"],
        "role": employee["role"],
        "status": employee["status"],
        "created_at": employee["created_at"],
        "updated_at": employee["updated_at"],
    }