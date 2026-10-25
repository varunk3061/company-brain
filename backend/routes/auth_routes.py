from fastapi import APIRouter, Depends, HTTPException, status

from database.connection import departments_collection, users_collection
from models.user_model import LoginRequest, LoginResponse, SessionUser
from services.access.policy import UserContext
from utils.auth import build_user_context, create_access_token, get_current_user
from utils.security import ACCESS_TOKEN_EXPIRE_MINUTES, verify_password

#-------------------------------------------------------------------------------------

router = APIRouter(prefix="/auth", tags=["Auth"])


def _session_user(ctx: UserContext) -> SessionUser:
    department = departments_collection.find_one({"code": ctx.department_code}, {"name": 1})

    return SessionUser(
        user_uuid=ctx.user_uuid, name=ctx.name, email=ctx.email,
        department_code=ctx.department_code,
        department_name=department["name"] if department else ctx.department_code,
        role_code=ctx.role_code, role_name=ctx.role_name,
        clearance=ctx.clearance, permissions=sorted(ctx.permissions),
    )

#-------------------------------------------------------------------------------------

@router.post("/login", response_model=LoginResponse)
def login(login_data: LoginRequest):
    """Authenticate any user (admin or employee) and return an access token."""

    email = str(login_data.email).strip().lower()
    password = login_data.password.get_secret_value()

    user = users_collection.find_one({"email": email})

    # Same error for unknown email and wrong password: no user enumeration.
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if user.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is blocked",
        )

    ctx = build_user_context(user)

    return LoginResponse(
        access_token=create_access_token(user),
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=_session_user(ctx),
    )


@router.get("/me", response_model=SessionUser)
def me(ctx: UserContext = Depends(get_current_user)):
    """Current user's profile and permissions, read fresh from the database."""

    return _session_user(ctx)
