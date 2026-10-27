from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from database.connection import (
    departments_collection, roles_collection, users_collection,
)
from models.user_model import UserCreate, UserUpdate, UserResponse
from services import audit_service
from utils.security import hash_password

#-------------------------------------------------------------------------------------

def _now():
    return datetime.now(timezone.utc)


def _not_found():
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")


def _conflict(message: str):
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)

#-------------------------------------------------------------------------------------

def user_response(user: dict, departments: dict | None = None, roles: dict | None = None) -> dict:
    """Safe fields only. Pass prefetched {code: name} maps when serialising many users."""

    if departments is None:
        departments = {d["code"]: d["name"] for d in departments_collection.find({}, {"code": 1, "name": 1})}
    if roles is None:
        roles = {r["code"]: r["name"] for r in roles_collection.find({}, {"code": 1, "name": 1})}

    return UserResponse(
        user_uuid=user["user_uuid"],
        name=user["name"],
        email=user["email"],
        department_code=user["department_code"],
        department_name=departments.get(user["department_code"], user["department_code"]),
        role_code=user["role_code"],
        role_name=roles.get(user["role_code"], user["role_code"]),
        status=user["status"],
        created_at=user["created_at"],
        updated_at=user["updated_at"],
    ).model_dump()


def _validate_position(department_code: str, role_code: str) -> None:
    """A role belongs to exactly one department; both must be active."""

    department = departments_collection.find_one({"code": department_code})
    role = roles_collection.find_one({"code": role_code})

    if not department or department["status"] != "active":
        raise HTTPException(status_code=422, detail="Department does not exist or is inactive.")
    if not role or role["status"] != "active":
        raise HTTPException(status_code=422, detail="Role does not exist or is inactive.")
    if role["department_code"] != department_code:
        raise HTTPException(status_code=422, detail="Role does not belong to the selected department.")


def _is_admin_role(role_code: str) -> bool:
    return roles_collection.count_documents({"code": role_code, "permissions": "users.manage"}) > 0


def _other_active_admins(excluding_uuid: str) -> int:
    admin_roles = [r["code"] for r in roles_collection.find({"permissions": "users.manage"}, {"code": 1})]
    return users_collection.count_documents({
        "role_code": {"$in": admin_roles}, "status": "active", "user_uuid": {"$ne": excluding_uuid},
    })

#-------------------------------------------------------------------------------------

def create_user(data: UserCreate, actor) -> dict:
    password = data.password.get_secret_value()

    if len(password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Password must not exceed 72 UTF-8 bytes.")

    _validate_position(data.department_code, data.role_code)

    now = _now()
    user = {
        "user_uuid": str(uuid4()),
        "name": data.name.strip(),
        "email": str(data.email).strip().lower(),
        "password_hash": hash_password(password),
        "department_code": data.department_code,
        "role_code": data.role_code,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }

    try:
        users_collection.insert_one(user)
    except DuplicateKeyError:
        raise _conflict("A user with this email already exists.")

    user_target = f"{user['name']} ({user['email']})"
    audit_service.record(
        actor, "user.create", user_target,
        after={"email": user["email"], "department_code": user["department_code"], "role_code": user["role_code"]},
    )
    return user_response(user)


def list_users(page: int, page_size: int, department_code=None, role_code=None, user_status=None) -> dict:
    filters = {}
    if department_code:
        filters["department_code"] = department_code
    if role_code:
        filters["role_code"] = role_code
    if user_status:
        filters["status"] = user_status

    users = users_collection.find(filters, {"_id": 0, "password_hash": 0}) \
        .sort("created_at", -1).skip((page - 1) * page_size).limit(page_size)

    departments = {d["code"]: d["name"] for d in departments_collection.find({}, {"code": 1, "name": 1})}
    roles = {r["code"]: r["name"] for r in roles_collection.find({}, {"code": 1, "name": 1})}

    return {
        "items": [user_response(u, departments, roles) for u in users],
        "total": users_collection.count_documents(filters),
        "page": page,
        "page_size": page_size,
    }


def get_user(user_uuid: str) -> dict:
    user = users_collection.find_one({"user_uuid": user_uuid})
    if not user:
        raise _not_found()
    return user_response(user)


def update_user(user_uuid: str, data: UserUpdate, actor) -> dict:
    user = users_collection.find_one({"user_uuid": user_uuid})
    if not user:
        raise _not_found()

    changes = data.model_dump(exclude_none=True)
    new_department = changes.get("department_code", user["department_code"])
    new_role = changes.get("role_code", user["role_code"])

    if "department_code" in changes or "role_code" in changes:
        _validate_position(new_department, new_role)

    # An admin must not lock themselves out, nor remove the last administrator.
    loses_admin = (
        user.get("status") == "active" and _is_admin_role(user["role_code"])
        and (changes.get("status") == "blocked" or not _is_admin_role(new_role))
    )
    if loses_admin:
        if user_uuid == actor.user_uuid:
            raise _conflict("You cannot block yourself or remove your own administrator role.")
        if not _other_active_admins(user_uuid):
            raise _conflict("This is the last active administrator.")

    if changes:
        changes["updated_at"] = _now()
        users_collection.update_one({"user_uuid": user_uuid}, {"$set": changes})
        user_target = f"{user.get('name', '')} ({user.get('email', '')})".strip() or user_uuid
        audit_service.record(
            actor, "user.update", user_target,
            before={k: user.get(k) for k in changes if k != "updated_at"},
            after={k: v for k, v in changes.items() if k != "updated_at"},
        )

    return get_user(user_uuid)


def delete_user(user_uuid: str, actor) -> dict:
    user = users_collection.find_one({"user_uuid": user_uuid})
    if not user:
        raise _not_found()

    if user.get("status") == "active" and _is_admin_role(user["role_code"]):
        if user_uuid == actor.user_uuid:
            raise _conflict("You cannot delete your own account.")
        if not _other_active_admins(user_uuid):
            raise _conflict("This is the last active administrator.")
    elif user_uuid == actor.user_uuid:
        raise _conflict("You cannot delete your own account.")

    users_collection.delete_one({"user_uuid": user_uuid})
    user_target = f"{user.get('name', '')} ({user.get('email', '')})".strip() or user_uuid
    audit_service.record(actor, "user.delete", user_target, before={"email": user["email"]})

    return {"message": "User deleted successfully.", "user_uuid": user_uuid}
