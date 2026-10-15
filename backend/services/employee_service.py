from uuid import uuid4
from datetime import datetime, timezone

from fastapi import HTTPException, status
from pymongo import DESCENDING

from pymongo.errors import DuplicateKeyError

from database.connection import employees_collection
from models.employee_model import (
    EmployeeCreate, EmployeeUpdate, EmployeeDepartment, EmployeeRole, EmployeeStatus,EmployeeResponse
)
from utils.security import hash_password

#-------------------------------------------------------------------------------------

def get_current_time():
    """Return the current UTC time """
    return datetime.now(timezone.utc)

#-------------------------------------------------------------------------------------

def employee_response(employee: dict) -> dict:
    """Return safe employee fields without internal database data."""

    return EmployeeResponse(
        employee_uuid=employee["employee_uuid"],
        name=employee["name"],
        email=employee["email"],
        department=employee["department"],
        role=employee["role"],
        status=employee["status"],
        created_at=employee["created_at"],
        updated_at=employee["updated_at"],
    ).model_dump()

#-------------------------------------------------------------------------------------

def create_employee(employee_data: EmployeeCreate) -> dict:
    """Create a new employee account"""

    email = str(employee_data.email).strip().lower()
    password = employee_data.password.get_secret_value()

    if len(password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=400, detail="Password must not exceed 72 UTF-8 bytes."
        )

    now = get_current_time()

    employee = {
        "employee_uuid" : str(uuid4()),
        "name" : employee_data.name.strip(),
        "email" : email,
        "password_hash" : hash_password(password),
        "department" : "Operations",
        "role" : "employee",
        "status" : "active",
        "created_at" : now,
        "updated_at" : now,
    }

    try:
        employees_collection.insert_one(employee)

    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An Employee with this email already exists."
        )

    return employee_response(employee)

#-------------------------------------------------------------------------------------

def list_employees(
    page: int = 1,
    page_size: int = 10,
    department: str | None = None,
    role: str | None = None,
    employee_status: str | None = None,
) -> dict:
    """Return employees with pagination and optional filters."""

    filters = {}

    if department:
        filters["department"] = department

    if role:
        filters["role"] = role

    if employee_status:
        filters["status"] = employee_status

    skip = (page - 1) * page_size

    employees = employees_collection.find(
        filters,
        {"_id": 0, "password_hash": 0},
    ).sort("created_at", -1).skip(skip).limit(page_size)

    total = employees_collection.count_documents(filters)

    return {
        "items": [
            employee_response(employee)
            for employee in employees
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }

#-------------------------------------------------------------------------------------

def get_employee(employee_uuid: str) -> dict:
    """Find one employee by UUID."""

    employee = employees_collection.find_one({
        "employee_uuid": employee_uuid
    })

    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found.",
        )

    return employee_response(employee)

#-------------------------------------------------------------------------------------

def update_employee(
    employee_uuid: str,
    employee_data: EmployeeUpdate,
) -> dict:
    """Update an employee's department, role, and status."""

    updated_data = employee_data.model_dump()
    updated_data["updated_at"] = get_current_time()

    result = employees_collection.update_one(
        {"employee_uuid": employee_uuid},
        {"$set": updated_data},
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found.",
        )

    return get_employee(employee_uuid)

#-------------------------------------------------------------------------------------

def delete_employee(employee_uuid: str) -> dict:
    """Delete an employee using their UUID."""

    result = employees_collection.delete_one({
        "employee_uuid": employee_uuid
    })

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found.",
        )

    return {
        "message": "Employee deleted successfully.",
        "employee_uuid": employee_uuid,
    }

#-------------------------------------------------------------------------------------