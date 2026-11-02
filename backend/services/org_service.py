# Add and edit departments (HR, IT, Sales…) and roles (Developer, HR Manager…).

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from database.connection import departments_collection, roles_collection, users_collection
from models.org_model import DepartmentCreate, DepartmentUpdate, RoleCreate, RoleUpdate
from services import audit_service

#-------------------------------------------------------------------------------------

_HIDE_ID = {"_id": 0}


def _now():
    return datetime.now(timezone.utc)


def _conflict(message: str):
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)


def _not_found(what: str):
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{what} not found.")

#-------------------------------------------------------------------------------------

def list_departments() -> list[dict]:
    return list(departments_collection.find({}, _HIDE_ID).sort("name", 1))


def get_department(code: str) -> dict:
    department = departments_collection.find_one({"code": code}, _HIDE_ID)
    if not department:
        raise _not_found("Department")
    return department


def create_department(data: DepartmentCreate, actor) -> dict:
    now = _now()
    department = {
        "department_uuid": str(uuid4()), "code": data.code, "name": data.name.strip(),
        "status": "active", "created_at": now, "updated_at": now,
    }
    try:
        departments_collection.insert_one(department)
    except DuplicateKeyError:
        raise _conflict("A department with this code already exists.")

    audit_service.record(actor, "department.create", data.code, after=data.model_dump())
    return get_department(data.code)


def update_department(code: str, data: DepartmentUpdate, actor) -> dict:
    before = get_department(code)
    changes = data.model_dump(exclude_none=True)

    if changes.get("status") == "inactive" and users_collection.count_documents(
        {"department_code": code, "status": "active"}
    ):
        raise _conflict("Department still has active users. Move or block them first.")

    if changes:
        changes["updated_at"] = _now()
        departments_collection.update_one({"code": code}, {"$set": changes})
        audit_service.record(
            actor, "department.update", code,
            before={k: before.get(k) for k in changes if k != "updated_at"},
            after={k: v for k, v in changes.items() if k != "updated_at"},
        )

    return get_department(code)

#-------------------------------------------------------------------------------------

def list_roles(department_code: str | None = None) -> list[dict]:
    query = {"department_code": department_code} if department_code else {}
    return list(roles_collection.find(query, _HIDE_ID).sort([("department_code", 1), ("name", 1)]))


def get_role(code: str) -> dict:
    role = roles_collection.find_one({"code": code}, _HIDE_ID)
    if not role:
        raise _not_found("Role")
    return role


def create_role(data: RoleCreate, actor) -> dict:
    department = departments_collection.find_one({"code": data.department_code})
    if not department or department["status"] != "active":
        raise HTTPException(status_code=422, detail="Department does not exist or is inactive.")

    now = _now()
    role = {
        "role_uuid": str(uuid4()), "code": data.code, "name": data.name.strip(),
        "department_code": data.department_code, "clearance": data.clearance,
        "permissions": sorted(set(data.permissions)), "status": "active",
        "created_at": now, "updated_at": now,
    }
    try:
        roles_collection.insert_one(role)
    except DuplicateKeyError:
        raise _conflict("A role with this code already exists.")

    audit_service.record(actor, "role.create", data.code, after=data.model_dump())
    return get_role(data.code)


def update_role(code: str, data: RoleUpdate, actor) -> dict:
    before = get_role(code)
    changes = data.model_dump(exclude_none=True)

    if "permissions" in changes:
        changes["permissions"] = sorted(set(changes["permissions"]))

    if changes.get("status") == "inactive" and users_collection.count_documents(
        {"role_code": code, "status": "active"}
    ):
        raise _conflict("Role is still assigned to active users. Reassign them first.")

    # Removing user-management rights must not leave the platform without an administrator.
    if "permissions" in changes and "users.manage" not in changes["permissions"] \
            and "users.manage" in before["permissions"]:
        if not _other_active_admins(excluding_role=code):
            raise _conflict("This is the only role that can manage users.")

    if changes:
        changes["updated_at"] = _now()
        roles_collection.update_one({"code": code}, {"$set": changes})
        audit_service.record(
            actor, "role.update", code,
            before={k: before.get(k) for k in changes if k != "updated_at"},
            after={k: v for k, v in changes.items() if k != "updated_at"},
        )

    return get_role(code)


def _other_active_admins(excluding_role: str) -> int:
    """Active users, outside `excluding_role`, whose role can manage users."""
    admin_roles = [
        r["code"] for r in roles_collection.find(
            {"permissions": "users.manage", "status": "active", "code": {"$ne": excluding_role}},
            {"code": 1},
        )
    ]
    return users_collection.count_documents({"role_code": {"$in": admin_roles}, "status": "active"})
