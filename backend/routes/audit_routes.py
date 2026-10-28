from typing import Annotated

from fastapi import APIRouter, Depends, Query

from database.connection import audit_log_collection, documents_collection, users_collection
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
        audit_log_collection.find({}, {"_id": 0})
        .sort("ts", -1).skip((page - 1) * page_size).limit(page_size)
    )

    actor_ids = {r["actor_uuid"] for r in rows if r.get("actor_uuid")}
    target_user_ids = {
        r.get("target") for r in rows
        if r.get("action", "").startswith("user.") and r.get("target")
    }
    all_user_ids = list(actor_ids | target_user_ids)
    user_records = {
        u["user_uuid"]: u
        for u in users_collection.find({"user_uuid": {"$in": all_user_ids}}, {"user_uuid": 1, "name": 1, "email": 1})
    }

    target_doc_ids = [
        r.get("target") for r in rows
        if r.get("action", "").startswith("document.") and r.get("target")
    ]
    doc_records = {
        d["document_uuid"]: d.get("document_name", d["document_uuid"])
        for d in documents_collection.find({"document_uuid": {"$in": target_doc_ids}}, {"document_uuid": 1, "document_name": 1})
    }

    items = []
    for r in rows:
        action = r.get("action", "")
        target = r.get("target", "")
        before = r.get("before") or {}
        after = r.get("after") or {}

        # Resolve RAG query target
        if action == "rag.ask":
            if target == "query" or not target:
                target = after.get("question") or before.get("question") or target or "query"

        # Resolve document target
        elif action.startswith("document."):
            if target in doc_records:
                target = doc_records[target]
            elif before.get("document_name"):
                target = before["document_name"]
            elif after.get("document_name"):
                target = after["document_name"]

        # Resolve user target
        elif action.startswith("user."):
            if target in user_records:
                u = user_records[target]
                target = f"{u.get('name', '')} ({u.get('email', '')})".strip() or target
            elif before.get("email") or after.get("email"):
                target = before.get("email") or after.get("email")

        actor_user = user_records.get(r.get("actor_uuid"))
        actor_name = actor_user["name"] if actor_user else ("System" if not r.get("actor_uuid") else "Deleted user")

        items.append({
            "ts": r["ts"],
            "actor_name": actor_name,
            "action": action,
            "target": target,
        })

    return {
        "items": items,
        "total": audit_log_collection.count_documents({}),
        "page": page,
        "page_size": page_size,
    }

