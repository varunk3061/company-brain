from typing import Annotated

from fastapi import APIRouter, Depends, Query

from database.connection import audit_log_collection, users_collection
from services.access.policy import UserContext
from utils.auth import require_permission

#-------------------------------------------------------------------------------------

router = APIRouter(prefix="/audit-logs", tags=["Audit"])

#-------------------------------------------------------------------------------------

@router.get("")
def list_audit_logs(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    _: UserContext = Depends(require_permission("audit.read")),
):
    """Admin change history, newest first. Only who/what/when: before/after payloads stay in the database."""

    rows = list(
        audit_log_collection.find({}, {"_id": 0, "before": 0, "after": 0})
        .sort("ts", -1).skip((page - 1) * page_size).limit(page_size)
    )

    actor_ids = {r["actor_uuid"] for r in rows if r.get("actor_uuid")}
    names = {
        u["user_uuid"]: u["name"]
        for u in users_collection.find({"user_uuid": {"$in": list(actor_ids)}}, {"user_uuid": 1, "name": 1})
    }

    return {
        "items": [
            {
                "ts": r["ts"],
                "actor_name": names.get(r.get("actor_uuid"), "System" if not r.get("actor_uuid") else "Deleted user"),
                "action": r["action"],
                "target": r["target"],
            }
            for r in rows
        ],
        "total": audit_log_collection.count_documents({}),
        "page": page,
        "page_size": page_size,
    }
