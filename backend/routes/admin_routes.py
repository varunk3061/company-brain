from fastapi import APIRouter, HTTPException, status, Depends, Query

from typing import Annotated

from database.connection import admins_collection

from models.employee_model import ( 
    AdminLoginRequest, EmployeeCreate, EmployeeUpdate,
    EmployeeResponse, EmployeeListResponse, EmployeeDepartment,
    EmployeeRole, EmployeeStatus
    )

from services.dashboard_service import get_dashboard_data

from services.employee_service import (
    create_employee, list_employees, get_employee, update_employee, delete_employee
)

from utils.security import verify_password
from utils.auth import (
    create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES,get_current_admin
)

#-------------------------------------------------------------------------------------

router = APIRouter()

#-------------------------------------------------------------------------------------

@router.post("/login")
def admin_login(login_data: AdminLoginRequest):
    """Authenticate an admin and return an access token"""

    email = str(login_data.email).strip().lower()
    password = login_data.password.get_secret_value()

    # Find the admin by normalized email
    admin = admins_collection.find_one({
        "email" : email
    })

    # use the same error for unknown email and incorrect password
    if not admin or not verify_password(
        password, admin["password_hash"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    access_token = create_access_token(admin)

    return {
        "access_token" : access_token,
        "token_type" : "bearer",
        "expires_in" : ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

#-------------------------------------------------------------------------------------

@router.get("/admin/me", tags=["Admin"])
def get_admin_profile(admin: dict = Depends(get_current_admin)):
    """Return the currently logged-in admin's profile."""

    return {
        "admin_uuid": admin["admin_uuid"],
        "name": admin.get("name", ""),
        "email": admin.get("email", ""),
        "role": admin.get("role", "admin"),
        "department": admin.get("department"),  # may be None for the .env-seeded admin
    }

#-------------------------------------------------------------------------------------

@router.get("/admin/dashboard", tags=["Admin"])
def get_admin_dashboard(admin: dict = Depends(get_current_admin)):
    """Return real stats and recent activity for the admin overview page."""

    return get_dashboard_data()

#-------------------------------------------------------------------------------------

# A. Create an employee
@router.post(
    "/employees",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Employee Management"],
)
def create_employee_route(
    employee_data: EmployeeCreate,
    admin: dict = Depends(get_current_admin),
):
    return create_employee(employee_data)

#-------------------------------------------------------------------------------------

# B. List employees with pagination and filters
@router.get(
    "/employees",
    response_model=EmployeeListResponse,
    tags=["Employee Management"],
)
def list_employees_route(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    department: EmployeeDepartment | None = None,
    role: EmployeeRole | None = None,
    employee_status: EmployeeStatus | None = Query(
        default=None,
        alias="status",
    ),
    admin: dict = Depends(get_current_admin),
):
    return list_employees(
        page=page,
        page_size=page_size,
        department=department,
        role=role,
        employee_status=employee_status,
    )

#-------------------------------------------------------------------------------------

# C. Get one employee by UUID
@router.get(
    "/employees/{employee_uuid}",
    response_model=EmployeeResponse,
    tags=["Employee Management"],
)
def get_employee_route(
    employee_uuid: str,
    admin: dict = Depends(get_current_admin),
):
    return get_employee(employee_uuid)

#-------------------------------------------------------------------------------------

# D. Update employee department, role, or status
@router.put(
    "/employees/{employee_uuid}",
    response_model=EmployeeResponse,
    tags=["Employee Management"],
)
def update_employee_route(
    employee_uuid: str,
    employee_data: EmployeeUpdate,
    admin: dict = Depends(get_current_admin),
):
    return update_employee(employee_uuid, employee_data)


# E. Delete an employee
@router.delete(
    "/employees/{employee_uuid}",
    tags=["Employee Management"],
)
def delete_employee_route(
    employee_uuid: str,
    admin: dict = Depends(get_current_admin),
):
    return delete_employee(employee_uuid)

#-------------------------------------------------------------------------------------