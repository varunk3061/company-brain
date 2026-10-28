from fastapi import APIRouter, Depends

from services.access.policy import UserContext
from services.dashboard_service import get_dashboard_data
from utils.auth import require_permission

#-------------------------------------------------------------------------------------

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/dashboard")
def get_admin_dashboard(_: UserContext = Depends(require_permission("users.manage"))):
    """Real stats and recent activity for the admin overview page."""

    return get_dashboard_data()
