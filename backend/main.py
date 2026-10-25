import os
import uuid

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from database.connection import (
    admins_collection,
    check_database_connection,
    users_collection,
)
from routes.audit_routes import router as audit_router
from routes.auth_routes import router as auth_router
from routes.dashboard_routes import router as dashboard_router
from routes.document_routes import router as document_router
from routes.org_routes import router as org_router
from routes.rag_routes import router as rag_router
from routes.user_routes import router as user_router
from services.org_seed import seed_org
from utils.security import hash_password

#------------------------------------------------------------------------------------------------

ADMIN_ROLE = "SYSTEM_ADMIN"
ADMIN_DEPARTMENT = "EXEC"

#------------------------------------------------------------------------------------------------

def create_initial_admin():
    """Create the first System Administrator on a brand-new install."""

    if users_collection.count_documents({"role_code": ADMIN_ROLE}) > 0:
        return

    if admins_collection.count_documents({}) > 0:
        # Existing install that has not been migrated: don't create a second admin identity.
        print("Legacy admins found. Run `python -m scripts.migrate_users --apply` to move them to `users`.")
        return

    admin_name = os.getenv("ADMIN_NAME")
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if not admin_name or not admin_email or not admin_password:
        raise RuntimeError(
            "Set ADMIN_NAME, ADMIN_EMAIL, and ADMIN_PASSWORD "
            "in .env before starting the application."
        )

    if len(admin_password) < 12:
        raise RuntimeError("ADMIN_PASSWORD must contain at least 12 characters.")

    if len(admin_password.encode("utf-8")) > 72:
        raise RuntimeError("ADMIN_PASSWORD must not exceed 72 UTF-8 bytes.")

    now = datetime.now(timezone.utc)

    users_collection.insert_one({
        "user_uuid": str(uuid.uuid4()),
        "name": admin_name.strip(),
        "email": admin_email.strip().lower(),
        "password_hash": hash_password(admin_password),
        "department_code": ADMIN_DEPARTMENT,
        "role_code": ADMIN_ROLE,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    })

    print("Initial admin created successfully.")

#------------------------------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    check_database_connection()
    seed_org()
    create_initial_admin()

    yield

#------------------------------------------------------------------------------------------------

app = FastAPI(
    title="Company Brain API",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(audit_router)
app.include_router(org_router)
app.include_router(user_router)
app.include_router(dashboard_router)
app.include_router(document_router)
app.include_router(rag_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#------------------------------------------------------------------------------------------------

@app.get("/")
def home():
    return {"message": "Company Brain API is running"}
