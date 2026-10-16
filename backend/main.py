import os
import uuid

from datetime import datetime, timezone
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

from database.connection import (
    check_database_connection,
    admins_collection,
)

from routes.admin_routes import router as admin_router
from routes.employee_routes import router as employee_router
from routes.document_routes import router as document_router

from utils.security import hash_password


load_dotenv()


def create_initial_admin():
    """Create the first admin if no admin account exists."""

    # Never create another initial admin if one already exists.
    if admins_collection.count_documents({}) > 0:
        print("An admin account already exists.")
        return

    admin_name = os.getenv("ADMIN_NAME")
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if not admin_name or not admin_email or not admin_password:
        raise RuntimeError(
            "Set ADMIN_NAME, ADMIN_EMAIL, and ADMIN_PASSWORD "
            "in .env before starting the application."
        )

    admin_email = admin_email.strip().lower()

    if len(admin_password) < 6 :
        raise RuntimeError(
            "ADMIN_PASSWORD must contain at least 12 characters."
        )

    if len(admin_password.encode("utf-8")) > 72:
        raise RuntimeError(
            "ADMIN_PASSWORD must not exceed 72 UTF-8 bytes."
        )

    now = datetime.now(timezone.utc)

    admin_document = {
        "admin_uuid": str(uuid.uuid4()),
        "name": admin_name.strip(),
        "email": admin_email,
        "password_hash": hash_password(admin_password),
        "role": "admin",
        "created_at": now,
        "updated_at": now,
    }

    # Only the password hash is stored.
    admins_collection.insert_one(admin_document)

    print("Initial admin created successfully.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    check_database_connection()
    create_initial_admin()

    yield


app = FastAPI(
    title="Admin and Employee Management API",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(admin_router)
app.include_router(employee_router)
app.include_router(document_router)


@app.get("/")
def home():
    return {
        "message": "Admin and Employee Management API is running"
    }