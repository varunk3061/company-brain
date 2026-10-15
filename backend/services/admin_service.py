from fastapi import HTTPException
from datetime import datetime, timezone
from uuid import uuid4

from database.connection import admins_collection
from utils.security import hash_password, verify_password, create_access_token


# ============================================================
# CREATE ADMIN
# ============================================================

def create_admin_service(admin_data):

    existing_user = admins_collection.find_one(
        {
            "email": admin_data.email.strip().lower()
        }
    )

    if existing_user:
        raise HTTPException(
            status_code=400, detail="Email already registered"
        )

    admin = {
        "admin_uuid": str(uuid4()),
        "name": admin_data.name,
        "email": admin_data.email.strip().lower(),
        "password": hash_password(admin_data.password),
        "role": "admin",
        "department": admin_data.department,
        "isActive": True,
        "createdAt": datetime.now(timezone.utc)
    }

    admins_collection.insert_one(admin)

    return {
        "message": "Admin created successfully",
        "admin_uuid": admin["admin_uuid"],
        "name":admin["name"],
        "email":admin["email"],
        "role":admin["role"]
    }


# ============================================================
# ADMIN LOGIN
# ============================================================

def login_admin_service(login_data):

    admin = admins_collection.find_one({
        "email": login_data.username.strip().lower(),
        "role": "admin",
        "isActive": True
    })

    if not admin or not verify_password(login_data.password, admin["password"]):
        raise HTTPException(
            status_code=401, detail="Invalid email or password"
        )

    access_token = create_access_token({
        "admin_uuid": admin["admin_uuid"],
        "role": admin["role"]
    })

    return {
        "message": "Admin login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "role": admin["role"]
    }