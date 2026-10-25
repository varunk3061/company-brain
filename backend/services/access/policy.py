"""Single source of truth for "may this user see this document?".

Every entry point (REST today; chat, retrieval and MCP later) must go through
`can_view` / `build_document_filter`. They encode the same rule and are kept in
lock-step by tests/test_policy.py.
"""

from dataclasses import dataclass, field

#-------------------------------------------------------------------------------------

LEVELS = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}

#-------------------------------------------------------------------------------------

@dataclass(frozen=True)
class UserContext:
    """Fresh, per-request view of a user: identity + org position + role-derived rights."""

    user_uuid: str
    name: str
    email: str
    department_code: str
    role_code: str
    role_name: str
    clearance: str
    permissions: frozenset = field(default_factory=frozenset)

    def has(self, permission: str) -> bool:
        return permission in self.permissions

#-------------------------------------------------------------------------------------

def _level(classification) -> int:
    """Unknown or missing classification is treated as restricted (deny by default)."""
    return LEVELS.get(classification, LEVELS["restricted"])


def _granted(ctx: UserContext, access: dict) -> bool:
    return (
        ctx.user_uuid in access.get("users", [])
        or ctx.role_code in access.get("roles", [])
        or ctx.department_code in access.get("departments", [])
    )


def can_view(ctx: UserContext, doc: dict) -> bool:
    """Decide visibility of one document."""

    level = _level(doc.get("classification"))

    if level <= LEVELS["internal"]:
        return True

    if _granted(ctx, doc.get("access") or {}):
        return True

    # Confidential: the owning department's members with enough clearance. Restricted: grants only.
    return (
        level == LEVELS["confidential"]
        and _level(ctx.clearance) >= LEVELS["confidential"]
        and doc.get("department_code") == ctx.department_code
    )


def build_document_filter(ctx: UserContext) -> dict:
    """Mongo filter equivalent to `can_view`. Uses only operators that Atlas `$vectorSearch` `filter` accepts,
    so the same filter runs on documents and, inside the vector query, on chunks (they carry a copy of the access fields)."""

    clauses = [
        {"classification": {"$in": ["public", "internal"]}},
        {"access.users": {"$eq": ctx.user_uuid}},
        {"access.roles": {"$eq": ctx.role_code}},
        {"access.departments": {"$eq": ctx.department_code}},
    ]

    if _level(ctx.clearance) >= LEVELS["confidential"]:
        clauses.append({"$and": [
            {"classification": {"$eq": "confidential"}},
            {"department_code": {"$eq": ctx.department_code}},
        ]})

    return {"$or": clauses}
