from datetime import datetime, timezone

from conftest import login
from database.connection import (
    admins_collection, documents_collection, employees_collection, users_collection,
)
from scripts import migrate_users
from utils.security import hash_password

NOW = datetime.now(timezone.utc)


def seed_legacy():
    admins_collection.insert_one({
        "admin_uuid": "a1", "name": "Old Admin", "email": "old.admin@nexora.com",
        "password_hash": hash_password("old-admin-password"), "role": "admin", "created_at": NOW,
    })
    base = {"created_at": NOW, "updated_at": NOW, "status": "active", "password_hash": hash_password("old-emp-password")}
    employees_collection.insert_many([
        {**base, "employee_uuid": "e1", "name": "Dev", "email": "dev@nexora.com", "department": "IT", "role": "Developer"},
        {**base, "employee_uuid": "e2", "name": "Mismatch", "email": "mm@nexora.com", "department": "IT", "role": "Finance"},
        {**base, "employee_uuid": "e3", "name": "Support", "email": "sup@nexora.com", "department": "Support", "role": "Tester"},
        {**base, "employee_uuid": "e4", "name": "Boss", "email": "boss@nexora.com", "department": "IT", "role": "Manager"},
    ])
    documents_collection.insert_one({
        "document_uuid": "d1", "document_name": "x.pdf", "last_update": NOW,
        "allowed_roles": ["HR", "Manager"], "file_path": "/x.pdf",
    })


def test_dry_run_writes_nothing(client):
    seed_legacy()
    migrate_users.main(apply=False)
    assert users_collection.count_documents({"email": "dev@nexora.com"}) == 0


def test_apply_imports_maps_and_preserves_logins(client):
    seed_legacy()
    migrate_users.main(apply=True)

    assert users_collection.find_one({"email": "dev@nexora.com"})["role_code"] == "DEVELOPER"
    assert users_collection.count_documents({"email": "mm@nexora.com"}) == 0  # role/department mismatch: fail closed
    assert users_collection.find_one({"email": "sup@nexora.com"})["department_code"] == "IT"  # Support -> IT
    assert users_collection.find_one({"email": "boss@nexora.com"})["role_code"] == "IT_MANAGER"

    login(client, "dev@nexora.com", "old-emp-password")
    login(client, "old.admin@nexora.com", "old-admin-password")

    doc = documents_collection.find_one({"document_uuid": "d1"})
    assert doc["access"]["roles"] == ["HR_GENERALIST", "IT_MANAGER"] and doc["needs_classification"] is True

    migrate_users.main(apply=True)  # idempotent
    assert users_collection.count_documents({"email": "dev@nexora.com"}) == 1
