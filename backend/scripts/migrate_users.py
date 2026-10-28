"""Move legacy `admins` / `employee` rows into `users` and map document roles.

    python -m scripts.migrate_users            # dry run: prints a report, writes nothing
    python -m scripts.migrate_users --apply    # performs the migration

Safe to re-run: rows whose email already exists in `users` are skipped. Legacy collections are
left untouched. Rows that cannot be mapped unambiguously are reported and NOT imported
(fail closed), so they cannot sign in until an admin recreates them.
"""

import sys
from datetime import datetime, timezone

from database.connection import (
    admins_collection, check_database_connection, client, documents_collection,
    employees_collection, roles_collection, users_collection,
)
from services.org_seed import ROLES, seed_org

#-------------------------------------------------------------------------------------

# Legacy employee role -> new role code (matched case-insensitively)
ROLE_MAP = {
    "Developer": "DEVELOPER",
    "Tester": "QA_ENGINEER",
    "DevOps": "DEVOPS_ENGINEER",
    "HR": "HR_GENERALIST",
    "Finance": "FINANCIAL_ANALYST",
    "Manager": "IT_MANAGER",
}

# Legacy document `allowed_roles` strings -> new role code
DOC_ROLE_MAP = {**ROLE_MAP, "Admin": "SYSTEM_ADMIN", "Engineering": "DEVELOPER"}

# Legacy department name -> new department code. "Support" is not in the org chart; its only user is a tester, who belongs in IT.
DEPT_MAP = {"IT": "IT", "HR": "HR", "Finance": "FIN", "Support": "IT"}

ADMIN_ROLE, ADMIN_DEPARTMENT = "SYSTEM_ADMIN", "EXEC"

#-------------------------------------------------------------------------------------

def _lookup(mapping: dict, value):
    """Case-insensitive, whitespace-tolerant lookup of a legacy value."""
    folded = {k.lower(): v for k, v in mapping.items()}
    return folded.get(str(value or "").strip().lower())


def _plan_users(role_department: dict):
    to_insert, skipped, rejected = [], [], []

    existing = {u["email"] for u in users_collection.find({}, {"email": 1})}

    for admin in admins_collection.find({}):
        row = _base(admin, admin["admin_uuid"], ADMIN_DEPARTMENT, ADMIN_ROLE, "active")
        (skipped if row["email"] in existing else to_insert).append(row)
        existing.add(row["email"])

    for emp in employees_collection.find({}):
        role_code = _lookup(ROLE_MAP, emp.get("role"))
        if not role_code:
            rejected.append((emp.get("email"), f"unknown role {emp.get('role')!r}"))
            continue
        department = _lookup(DEPT_MAP, emp.get("department"))
        if role_department[role_code] != department:
            rejected.append((
                emp.get("email"),
                f"department {emp.get('department')!r} does not match role {emp.get('role')!r} "
                f"(belongs to {role_department[role_code]})",
            ))
            continue
        row = _base(emp, emp["employee_uuid"], department, role_code, emp.get("status", "active"))
        (skipped if row["email"] in existing else to_insert).append(row)
        existing.add(row["email"])

    return to_insert, skipped, rejected


def _base(src: dict, uuid_value: str, department: str, role: str, status: str) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "user_uuid": uuid_value,
        "name": src["name"],
        "email": src["email"].strip().lower(),
        "password_hash": src["password_hash"],
        "department_code": department,
        "role_code": role,
        "status": status if status in ("active", "blocked") else "blocked",
        "created_at": src.get("created_at") or src.get("createdAt") or now,
        "updated_at": src.get("updated_at") or src.get("created_at") or src.get("createdAt") or now,
    }


def _plan_documents():
    updates, unmapped = [], []

    for doc in documents_collection.find({"classification": {"$exists": False}}):
        roles, bad = [], []
        for legacy in doc.get("allowed_roles", []):
            mapped = _lookup(DOC_ROLE_MAP, legacy)
            (roles if mapped else bad).append(mapped or legacy)
        updates.append((doc["document_uuid"], sorted(set(roles))))
        if bad:
            unmapped.append((doc.get("document_name"), bad))

    return updates, unmapped

#-------------------------------------------------------------------------------------

def main(apply: bool) -> None:
    if apply:
        check_database_connection()  # ping + indexes
        seed_org()
        role_department = {r["code"]: r["department_code"] for r in roles_collection.find({})}
    else:
        # Dry run is strictly read-only: no indexes, no seeding. Use the seed definition for mapping.
        client.admin.command("ping")
        role_department = {code: dept for code, _, dept, _, _ in ROLES}

    to_insert, skipped, rejected = _plan_users(role_department)
    doc_updates, doc_unmapped = _plan_documents()

    print(f"Mode: {'APPLY' if apply else 'DRY RUN'}")
    print(f"Users to import: {len(to_insert)} | already present: {len(skipped)} | NOT imported: {len(rejected)}")
    for email, reason in rejected:
        print(f"  ! {email}: {reason}")
    print(f"Documents to migrate: {len(doc_updates)}")
    for name, legacy in doc_unmapped:
        print(f"  ! {name}: legacy roles with no mapping dropped: {legacy}")

    if not apply:
        print("Nothing written. Re-run with --apply.")
        return

    if to_insert:
        users_collection.insert_many(to_insert)

    for document_uuid, roles in doc_updates:
        documents_collection.update_one(
            {"document_uuid": document_uuid},
            {"$set": {
                "department_code": None,
                "classification": "internal",
                "access": {"departments": [], "roles": roles, "users": []},
                "needs_classification": True,
            }},
        )

    print("Done. Legacy collections and `allowed_roles` were left in place.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
