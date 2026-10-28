from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from models.user_model import (
    UserCreate, UserUpdate, UserResponse, UserListResponse, UserStatus,
)
from services import user_service
from services.access.policy import UserContext
from utils.auth import require_permission

#-------------------------------------------------------------------------------------

router = APIRouter(prefix="/users", tags=["User Management"])

#-------------------------------------------------------------------------------------

@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(data: UserCreate, actor: UserContext = Depends(require_permission("users.manage"))):
    return user_service.create_user(data, actor)


@router.get("", response_model=UserListResponse)
def list_users(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    department_code: str | None = None,
    role_code: str | None = None,
    user_status: UserStatus | None = Query(default=None, alias="status"),
    _: UserContext = Depends(require_permission("users.manage")),
):
    return user_service.list_users(page, page_size, department_code, role_code, user_status)


@router.get("/{user_uuid}", response_model=UserResponse)
def get_user(user_uuid: str, _: UserContext = Depends(require_permission("users.manage"))):
    return user_service.get_user(user_uuid)


@router.put("/{user_uuid}", response_model=UserResponse)
def update_user(user_uuid: str, data: UserUpdate, actor: UserContext = Depends(require_permission("users.manage"))):
    return user_service.update_user(user_uuid, data, actor)


@router.delete("/{user_uuid}")
def delete_user(user_uuid: str, actor: UserContext = Depends(require_permission("users.manage"))):
    return user_service.delete_user(user_uuid, actor)
