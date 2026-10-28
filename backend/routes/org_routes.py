from fastapi import APIRouter, Depends

from models.org_model import (
    DepartmentCreate, DepartmentResponse, DepartmentUpdate,
    RoleCreate, RoleResponse, RoleUpdate,
)
from services import org_service
from services.access.policy import UserContext
from utils.auth import get_current_user, require_permission

#-------------------------------------------------------------------------------------

router = APIRouter(tags=["Organisation"])

#-------------------------------------------------------------------------------------
# Reading the org tree is open to any signed-in user (needed to render dropdowns and names);
# changing it needs `org.manage`.

@router.get("/departments", response_model=list[DepartmentResponse])
def list_departments(_: UserContext = Depends(get_current_user)):
    return org_service.list_departments()


@router.post("/departments", response_model=DepartmentResponse, status_code=201)
def create_department(data: DepartmentCreate, actor: UserContext = Depends(require_permission("org.manage"))):
    return org_service.create_department(data, actor)


@router.put("/departments/{code}", response_model=DepartmentResponse)
def update_department(code: str, data: DepartmentUpdate, actor: UserContext = Depends(require_permission("org.manage"))):
    return org_service.update_department(code, data, actor)

#-------------------------------------------------------------------------------------

@router.get("/roles", response_model=list[RoleResponse])
def list_roles(department_code: str | None = None, _: UserContext = Depends(get_current_user)):
    return org_service.list_roles(department_code)


@router.post("/roles", response_model=RoleResponse, status_code=201)
def create_role(data: RoleCreate, actor: UserContext = Depends(require_permission("org.manage"))):
    return org_service.create_role(data, actor)


@router.put("/roles/{code}", response_model=RoleResponse)
def update_role(code: str, data: RoleUpdate, actor: UserContext = Depends(require_permission("org.manage"))):
    return org_service.update_role(code, data, actor)
