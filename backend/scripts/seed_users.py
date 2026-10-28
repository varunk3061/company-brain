"""Create users from a CSV sheet (default: scripts/data/users.csv) in the `users` collection.

    python -m scripts.seed_users                         # dry run: prints a report, writes nothing
    python -m scripts.seed_users --apply                 # inserts the users
    python -m scripts.seed_users --csv path/to/file.csv  # use another sheet

Every new user gets a fresh user_uuid and the default password 123456 (bcrypt-hashed, same as the API).
department_code / role_code are resolved from the `departments` and `roles` collections.
Safe to re-run: emails already in `users` are skipped. Rows that cannot be mapped are reported and
NOT imported (fail closed).
"""

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from database.connection import (
    check_database_connection, client, departments_collection, roles_collection, users_collection,
)
from services.org_seed import DEPARTMENTS, ROLES, seed_org
from utils.security import hash_password

#-------------------------------------------------------------------------------------

DEFAULT_CSV = Path(__file__).parent / "data" / "users.csv"
DEFAULT_PASSWORD = "123456"

# Sheet values whose text differs from the department/role names in the DB (matched case-insensitively)
DEPT_ALIASES = {"leadership / administration": "EXEC"}
ROLE_ALIASES = {
    "ceo / admin": "CEO",
    "relationship manager (rm)": "RELATIONSHIP_MANAGER",
}

# users.status only allows active | blocked
STATUS_MAP = {"active": "active", "inactive": "blocked", "blocked": "blocked"}

#-------------------------------------------------------------------------------------

def _norm(value) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _load_org(apply: bool):
    """Return (departments, roles) as lists of dicts, from the DB or, on an empty dry run, the seed definition."""
    departments = list(departments_collection.find({}, {"_id": 0}))
    roles = list(roles_collection.find({}, {"_id": 0}))

    if not roles and not apply:
        print("Note: org collections are empty; dry run is using the seed definition (services/org_seed.py).")
        departments = [{"code": c, "name": n, "status": "active"} for c, n in DEPARTMENTS]
        roles = [{"code": c, "name": n, "department_code": d, "status": "active"} for c, n, d, _, _ in ROLES]

    return departments, roles


def _build_lookups(departments, roles):
    dept_by_key = {}
    for d in departments:
        dept_by_key[_norm(d["code"])] = d
        dept_by_key[_norm(d["name"])] = d

    role_by_code = {r["code"]: r for r in roles}
    roles_by_name = {}
    for r in roles:
        roles_by_name.setdefault(_norm(r["name"]), []).append(r)

    return dept_by_key, role_by_code, roles_by_name


def _resolve(row, dept_by_key, role_by_code, roles_by_name):
    """Return (department_code, role_code) or raise ValueError with the reason."""
    dept_raw, role_raw = row["department"], row["role"]

    alias = DEPT_ALIASES.get(_norm(dept_raw))
    department = dept_by_key.get(_norm(alias)) if alias else dept_by_key.get(_norm(dept_raw))
    if not department:
        raise ValueError(f"department {dept_raw!r} not found")
    if department.get("status", "active") != "active":
        raise ValueError(f"department {department['code']} is inactive")

    alias = ROLE_ALIASES.get(_norm(role_raw))
    if alias:
        role = role_by_code.get(alias)
    else:
        candidates = [r for r in roles_by_name.get(_norm(role_raw), []) if r["department_code"] == department["code"]]
        role = candidates[0] if candidates else None
    if not role:
        raise ValueError(f"role {role_raw!r} not found in department {department['code']}")
    if role["department_code"] != department["code"]:
        raise ValueError(f"role {role['code']} belongs to {role['department_code']}, not {department['code']}")
    if role.get("status", "active") != "active":
        raise ValueError(f"role {role['code']} is inactive")

    return department["code"], role["code"]


def _plan(csv_path: Path, departments, roles):
    dept_by_key, role_by_code, roles_by_name = _build_lookups(departments, roles)
    existing = {u["email"] for u in users_collection.find({}, {"email": 1})}

    password_hash = hash_password(DEFAULT_PASSWORD)
    now = datetime.now(timezone.utc)
    to_insert, skipped, rejected = [], [], []

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            email = row["email"].strip().lower()
            if not email:
                continue
            if email in existing:
                skipped.append(email)
                continue

            try:
                department_code, role_code = _resolve(row, dept_by_key, role_by_code, roles_by_name)
            except ValueError as err:
                rejected.append((email, str(err)))
                continue

            status = STATUS_MAP.get(_norm(row.get("status")))
            if not status:
                rejected.append((email, f"unknown status {row.get('status')!r}"))
                continue

            to_insert.append({
                "user_uuid": str(uuid4()),
                "name": row["name"].strip(),
                "email": email,
                "password_hash": password_hash,
                "department_code": department_code,
                "role_code": role_code,
                "status": status,
                "created_at": now,
                "updated_at": now,
            })
            existing.add(email)

    return to_insert, skipped, rejected

#-------------------------------------------------------------------------------------

def main(apply: bool, csv_path: Path) -> None:
    if not csv_path.exists():
        sys.exit(f"CSV not found: {csv_path}")

    if apply:
        check_database_connection()  # ping + indexes (unique email / user_uuid)
        seed_org()                   # inserts any missing departments/roles; never overwrites
    else:
        client.admin.command("ping")

    departments, roles = _load_org(apply)
    to_insert, skipped, rejected = _plan(csv_path, departments, roles)

    print(f"Mode: {'APPLY' if apply else 'DRY RUN'}   CSV: {csv_path}")
    print(f"Users to create: {len(to_insert)} | already present: {len(skipped)} | NOT created: {len(rejected)}")
    for u in to_insert:
        print(f"  + {u['email']:<44} {u['department_code']:<6} {u['role_code']:<22} {u['status']}")
    for email in skipped:
        print(f"  = {email} (already exists)")
    for email, reason in rejected:
        print(f"  ! {email}: {reason}")

    if not apply:
        print("Nothing written. Re-run with --apply.")
        return

    if to_insert:
        users_collection.insert_many(to_insert)
    print(f"Done. Created {len(to_insert)} users with password {DEFAULT_PASSWORD!r}.")


if __name__ == "__main__":
    args = sys.argv[1:]
    path = DEFAULT_CSV
    if "--csv" in args:
        path = Path(args[args.index("--csv") + 1])
    main(apply="--apply" in args, csv_path=path)
