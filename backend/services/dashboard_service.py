from datetime import datetime, timezone

from database.connection import employees_collection, documents_collection

#-------------------------------------------------------------------------------------

ACTIVITY_LIMIT = 10

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
        "total_users": employees_collection.count_documents({}),
        "users_added_this_month": employees_collection.count_documents(
            {"created_at": {"$gte": month_start}}
        ),
        "blocked_users": employees_collection.count_documents({"status": "blocked"}),
        "indexed_documents": documents_collection.count_documents({}),
        "documents_with_roles": documents_collection.count_documents(
            {"allowed_roles.0": {"$exists": True}}
        ),
        # Not recorded anywhere yet.
        "daily_rag_queries": 0,
        "avg_latency_ms": None,
        "security_status": None,
    }

    # --- Recent activity (built from existing records) --------------------------------
    activity = []

    recent_employees = employees_collection.find(
        {},
        {"_id": 0, "employee_uuid": 1, "name": 1, "department": 1, "created_at": 1},
    ).sort("created_at", -1).limit(ACTIVITY_LIMIT)

    for employee in recent_employees:
        activity.append({
            "id": f"emp-{employee.get('employee_uuid')}",
            "type": "user-add",
            "event": f"Added employee account: {employee.get('name') or '-'}",
            "actor": employee.get("name"),
            "dept": employee.get("department"),
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
