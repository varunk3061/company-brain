from fastapi import APIRouter, Depends, HTTPException, status

from database.connection import departments_collection, users_collection
from models.user_model import LoginRequest, LoginResponse, SessionUser
from services.access.policy import UserContext
from utils.auth import build_user_context, create_access_token, get_current_user
from utils.security import ACCESS_TOKEN_EXPIRE_MINUTES, hash_password, verify_password

#-------------------------------------------------------------------------------------

router = APIRouter(prefix="/auth", tags=["Auth"])

# Checked when the email is unknown, so that case costs the same bcrypt time as a wrong password.
DUMMY_HASH = hash_password("timing-equalisation-only")


def _session_user(ctx: UserContext) -> SessionUser:
    department = departments_collection.find_one({"code": ctx.department_code}, {"name": 1})

    return SessionUser(
        user_uuid=ctx.user_uuid, name=ctx.name, email=ctx.email,
        department_code=ctx.department_code,
        department_name=department["name"] if department else ctx.department_code, #it is ternary operator, if department is not None then get the name else return the department code
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

    # Same error and same bcrypt cost for unknown email and wrong password: no user enumeration.
    stored_hash = (user or {}).get("password_hash") or DUMMY_HASH #means if user is there then get the password hash else return the dummy hash
    password_ok = verify_password(password, stored_hash)

    if not user or not user.get("password_hash") or not password_ok:
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
