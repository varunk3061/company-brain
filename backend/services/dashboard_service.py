from datetime import datetime, timezone

from database.connection import users_collection, documents_collection

#-------------------------------------------------------------------------------------

ACTIVITY_LIMIT = 5

#-------------------------------------------------------------------------------------

def _as_utc(value):
    """MongoDB returns naive UTC datetimes; mark them as UTC so the browser reads them correctly."""

    if not isinstance(value, datetime):
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value

#-------------------------------------------------------------------------------------

def get_dashboard_data() -> dict:
    """Read-only summary for the admin overview page."""

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # --- Stats -----------------------------------------------------------------------
    stats = {
        "total_users": users_collection.count_documents({}),
        "users_added_this_month": users_collection.count_documents(
            {"created_at": {"$gte": month_start}}
        ),
        "blocked_users": users_collection.count_documents({"status": "blocked"}),
        "indexed_documents": documents_collection.count_documents({}),
        "documents_classified": documents_collection.count_documents(
            {"needs_classification": {"$ne": True}}
        ),
        # Not recorded anywhere yet.
        "daily_rag_queries": 0,
        "avg_latency_ms": None,
        "security_status": None,
    }

    # --- Recent activity (built from existing records) --------------------------------
    activity = []

    recent_employees = users_collection.find(
        {},
        {"_id": 0, "user_uuid": 1, "name": 1, "department_code": 1, "created_at": 1},
    ).sort("created_at", -1).limit(ACTIVITY_LIMIT)

    for employee in recent_employees:
        activity.append({
            "id": f"emp-{employee.get('user_uuid')}",
            "type": "user-add",
            "event": f"Added user account: {employee.get('name') or '-'}",
            "actor": employee.get("name"),
            "dept": employee.get("department_code"),
            "status": "Created",
            "timestamp": _as_utc(employee.get("created_at")),
        })

    recent_documents = documents_collection.find(
        {},
        {"_id": 0, "document_uuid": 1, "document_name": 1, "category": 1, "last_update": 1},
    ).sort("last_update", -1).limit(ACTIVITY_LIMIT)

    for document in recent_documents:
        activity.append({
            "id": f"doc-{document.get('document_uuid')}",
            "type": "upload",
            "event": f"Document registered: {document.get('document_name') or '-'}",
            "actor": None,
            "dept": document.get("category"),
            "status": "Registered",
            "timestamp": _as_utc(document.get("last_update")),
        })

    min_time = datetime.min.replace(tzinfo=timezone.utc)
    activity.sort(key=lambda row: row["timestamp"] or min_time, reverse=True)

    return {
        "stats": stats,
        "activity": activity[:ACTIVITY_LIMIT],
    }
