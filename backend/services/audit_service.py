from datetime import datetime, timezone

from database.connection import audit_log_collection

#-------------------------------------------------------------------------------------

def record(actor, action: str, target: str, before=None, after=None) -> None:
    """Append one admin-change row. `actor` is a UserContext (or None for system actions)."""

    audit_log_collection.insert_one({
        "ts": datetime.now(timezone.utc),
        "actor_uuid": actor.user_uuid if actor else None,
        "action": action,
        "target": target,
        "before": before,
        "after": after,
    })
