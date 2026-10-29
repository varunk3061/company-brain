"""Assign owner department, classification and role/user grants to documents that are already uploaded,
using the dataset manifest (default: scripts/data/documents_manifest.csv).

    python -m scripts.assign_document_access                       # dry run: prints the plan, writes nothing
    python -m scripts.assign_document_access --apply               # applies it
    python -m scripts.assign_document_access --manifest m.csv --users u.csv

How it works
- Documents in MongoDB are matched to manifest rows by file name (case-insensitive).
- Manifest department / role names are resolved to the codes in the `departments` / `roles`
  collections (same aliases as scripts/seed_users.py, e.g. "CEO / Admin" -> CEO).
- `allowed_user_ids` (U06 ...) are resolved through the users sheet (user_id -> email -> user_uuid).
- `ALL` means no explicit grant is needed for public/internal documents (everyone may read them);
  for a confidential/restricted document it grants every department.
- Each change is written by services.document_service.update_document_access, the same code as
  PATCH /api/documents/{uuid}/access: chunks and Neo4j are kept in step and an audit row is written
  (actor = system). Nothing is re-uploaded or re-embedded.

Fail closed: a row whose department, classification, role or user cannot be resolved is reported
and NOT applied. Documents already matching the manifest are left alone, so re-running is safe.
"""

import csv
import re
import sys
from pathlib import Path

from database.connection import (
    client, departments_collection, documents_chunk_collection, documents_collection,
    roles_collection, users_collection,
)
from models.document_model import AccessGrants, DocumentAccessUpdate
from services.access.policy import LEVELS, UserContext, can_view

#-------------------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"
DEFAULT_MANIFEST = DATA_DIR / "documents_manifest.csv"
DEFAULT_USERS = DATA_DIR / "users.csv"

# Sheet names that differ from the names stored in `departments` / `roles` (same as scripts/seed_users.py).
DEPT_ALIASES = {"leadership / administration": "EXEC", "legal & compliance": "LEGAL", "finance": "FIN"}
ROLE_ALIASES = {
    "ceo / admin": "CEO",
    "relationship manager (rm)": "RELATIONSHIP_MANAGER",
}

#-------------------------------------------------------------------------------------

def _norm(value) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _file_key(name) -> str:
    """Looser file-name key (letters and digits only) used when the exact name does not match."""
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())


def _split(value) -> list:
    return [part.strip() for part in str(value or "").split("|") if part.strip()]


def _read_csv(path: Path) -> list:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

#-------------------------------------------------------------------------------------

class Resolver:
    """Turns manifest text into the codes / uuids stored in MongoDB."""

    def __init__(self, users_sheet: list):
        self.departments = list(departments_collection.find({}, {"_id": 0}))
        self.roles = list(roles_collection.find({}, {"_id": 0}))

        self.dept_by_key = {}
        for d in self.departments:
            self.dept_by_key[_norm(d["code"])] = d
            self.dept_by_key[_norm(d["name"])] = d

        self.role_by_code = {r["code"]: r for r in self.roles}
        self.role_by_name = {}
        for r in self.roles:
            self.role_by_name.setdefault(_norm(r["name"]), []).append(r)

        self.email_by_sheet_id = {
            row["user_id"].strip(): row["email"].strip().lower()
            for row in users_sheet if row.get("user_id") and row.get("email")
        }

    def department(self, raw: str) -> str:
        key = _norm(raw)
        alias = DEPT_ALIASES.get(key)
        department = self.dept_by_key.get(_norm(alias) if alias else key)
        if not department:
            raise ValueError(f"department {raw!r} not found")
        if department.get("status", "active") != "active":
            raise ValueError(f"department {department['code']} is inactive")
        return department["code"]

    def role(self, raw: str) -> str:
        key = _norm(raw)
        alias = ROLE_ALIASES.get(key)
        if alias:
            role = self.role_by_code.get(alias)
        else:
            matches = self.role_by_name.get(key, [])
            if len(matches) > 1:
                raise ValueError(f"role name {raw!r} is ambiguous ({', '.join(r['code'] for r in matches)})")
            role = matches[0] if matches else None
        if not role:
            raise ValueError(f"role {raw!r} not found")
        return role["code"]

    def user(self, sheet_id: str) -> str:
        email = self.email_by_sheet_id.get(sheet_id)
        if not email:
            raise ValueError(f"user id {sheet_id!r} is not in the users sheet")
        user = users_collection.find_one({"email": email}, {"_id": 0, "user_uuid": 1})
        if not user:
            raise ValueError(f"user {sheet_id} ({email}) does not exist in `users`")
        return user["user_uuid"]

#-------------------------------------------------------------------------------------

def _target_for(row: dict, resolver: Resolver) -> dict:
    """Return the access settings for one manifest row, or raise ValueError with the reason."""

    classification = _norm(row.get("classification"))
    if classification not in LEVELS:
        raise ValueError(f"unknown classification {row.get('classification')!r}")

    department_code = resolver.department(row.get("department"))

    role_names = _split(row.get("allowed_roles"))
    everyone = any(_norm(r) == "all" for r in role_names)

    departments, roles = [], []
    if everyone:
        if LEVELS[classification] >= LEVELS["confidential"]:
            departments = [d["code"] for d in resolver.departments if d.get("status", "active") == "active"]
    else:
        roles = [resolver.role(name) for name in role_names]

    users = [resolver.user(uid) for uid in _split(row.get("allowed_user_ids"))]

    return {
        "department_code": department_code,
        "classification": classification,
        "access": {
            "departments": list(dict.fromkeys(departments)),
            "roles": list(dict.fromkeys(roles)),
            "users": list(dict.fromkeys(users)),
        },
        "everyone": everyone,
    }


def _same(document: dict, target: dict) -> bool:
    access = document.get("access") or {}
    return (
        document.get("department_code") == target["department_code"]
        and document.get("classification") == target["classification"]
        and not document.get("needs_classification", False)
        and all(sorted(access.get(k, [])) == sorted(target["access"][k]) for k in ("departments", "roles", "users"))
    )


def _extra_roles(target: dict, roles: list) -> list:
    """Roles the current policy would let read this document although the manifest does not list them
    (it happens through the 'same department + confidential clearance' rule)."""

    if target["everyone"]:
        return []

    doc = {k: target[k] for k in ("department_code", "classification", "access")}
    extra = []
    for role in roles:
        if role.get("status", "active") != "active" or role["code"] in target["access"]["roles"]:
            continue
        ctx = UserContext(
            user_uuid="-", name="-", email="-", department_code=role["department_code"],
            role_code=role["code"], role_name=role["name"], clearance=role.get("clearance", "internal"),
        )
        if can_view(ctx, doc):
            extra.append(role["code"])
    return extra


def _match_documents(manifest: list) -> tuple:
    """Pair manifest rows with stored documents. Returns (pairs, missing_rows, unmatched_documents)."""

    documents = list(documents_collection.find(
        {}, {"_id": 0, "document_uuid": 1, "document_name": 1, "department_code": 1,
             "classification": 1, "access": 1, "needs_classification": 1},
    ))
    by_name, by_key = {}, {}
    for d in documents:
        by_name.setdefault(_norm(d.get("document_name")), []).append(d)
        by_key.setdefault(_file_key(d.get("document_name")), []).append(d)

    pairs, missing, used = [], [], set()
    for row in manifest:
        matches = by_name.get(_norm(row.get("filename"))) or by_key.get(_file_key(row.get("filename"))) or []
        if not matches:
            missing.append(row)
        for d in matches:
            pairs.append((row, d))
            used.add(d["document_uuid"])

    unmatched = [d for d in documents if d["document_uuid"] not in used]
    return pairs, missing, unmatched

#-------------------------------------------------------------------------------------

def main(apply: bool, manifest_path: Path, users_path: Path) -> None:
    for path in (manifest_path, users_path):
        if not path.exists():
            sys.exit(f"CSV not found: {path}")

    client.admin.command("ping")

    manifest = _read_csv(manifest_path)
    resolver = Resolver(_read_csv(users_path))
    if not resolver.roles:
        sys.exit("The `roles` collection is empty. Start the backend once (it seeds the org) and re-run.")

    pairs, missing, unmatched = _match_documents(manifest)

    planned, unchanged, rejected, warnings = [], [], [], []
    for row, document in pairs:
        name = document.get("document_name")
        try:
            target = _target_for(row, resolver)
        except ValueError as err:
            rejected.append((name, str(err)))
            continue

        extra = _extra_roles(target, resolver.roles)
        if extra:
            warnings.append(f"{name}: also readable by {', '.join(extra)} (same-department rule), "
                            "although the manifest does not list them")
        if _split(row.get("project_ids")):
            warnings.append(f"{name}: project gate {row['project_ids']} is not enforced by the current policy")

        (unchanged if _same(document, target) else planned).append((document, target))

    print(f"Mode: {'APPLY' if apply else 'DRY RUN'}   Manifest: {manifest_path}")
    print(f"To update: {len(planned)} | already correct: {len(unchanged)} | NOT applied: {len(rejected)} | "
          f"manifest rows without a document: {len(missing)} | documents not in manifest: {len(unmatched)}\n")

    for document, target in planned:
        a = target["access"]
        print(f"  + {document['document_name']}")
        print(f"      dept={target['department_code']}  class={target['classification']}  "
              f"roles={a['roles'] or '-'}  departments={a['departments'] or '-'}  users={len(a['users'])}")
    for document, _ in unchanged:
        print(f"  = {document['document_name']} (already correct)")
    for name, reason in rejected:
        print(f"  ! {name}: {reason}")
    for row in missing:
        print(f"  ? {row.get('filename')}: not uploaded yet")
    for document in unmatched:
        print(f"  - {document.get('document_name')}: not in the manifest (left unchanged)")

    if warnings:
        print("\nWarnings (access model limits, not errors):")
        for line in warnings:
            print(f"  * {line}")

    if not apply:
        print("\nNothing written. Re-run with --apply.")
        return

    # Imported here so a dry run does not need the Neo4j / storage settings.
    from services.document_service import update_document_access
    from services.rag_service import chunk_access_fields

    done, failed = 0, []
    for document, target in planned:
        try:
            update_document_access(
                document["document_uuid"],
                DocumentAccessUpdate(
                    department_code=target["department_code"],
                    classification=target["classification"],
                    access=AccessGrants(**target["access"]),
                ),
                actor=None,  # recorded as a system action in the audit log
            )
            # update_document_access refreshes the chunks' `access`; also refresh the older flat copies
            # (allowed_roles/...) so nothing reading them sees stale values.
            updated = documents_collection.find_one({"document_uuid": document["document_uuid"]}, {"_id": 0})
            documents_chunk_collection.update_many(
                {"document_uuid": document["document_uuid"]}, {"$set": chunk_access_fields(updated)},
            )
            done += 1
        except Exception as exc:  # report and continue with the other documents
            failed.append((document["document_name"], getattr(exc, "detail", None) or str(exc)))

    for name, reason in failed:
        print(f"  ! FAILED {name}: {reason}")
    print(f"\nDone. Updated {done} document(s), {len(failed)} failed.")


if __name__ == "__main__":
    args = sys.argv[1:]

    def _arg(flag: str, default: Path) -> Path:
        return Path(args[args.index(flag) + 1]) if flag in args else default

    main(
        apply="--apply" in args,
        manifest_path=_arg("--manifest", DEFAULT_MANIFEST),
        users_path=_arg("--users", DEFAULT_USERS),
    )
