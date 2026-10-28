from datetime import datetime, timezone, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

from database.connection import users_collection, roles_collection
from services.access.policy import UserContext
from utils.security import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

#-------------------------------------------------------------------------------------------------

bearer_scheme = HTTPBearer(auto_error=False)

#-------------------------------------------------------------------------------------------------

def create_access_token(user: dict) -> str:
    """Create a signed JWT. It carries identity only; rights are re-read from the DB on every request."""

    now = datetime.now(timezone.utc)

    payload = {
        "sub": user["user_uuid"],
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

#-------------------------------------------------------------------------------------------------

def verify_access_token(token: str):
    """Decode a token or return None if it is invalid or expired."""

    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None

#-------------------------------------------------------------------------------------------------

def build_user_context(user: dict) -> UserContext:
    """Combine a users row with its role's current clearance and permissions."""

    role = roles_collection.find_one({"code": user.get("role_code")})

    if not role or role.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has no active role.",
        )

    return UserContext(
        user_uuid=user["user_uuid"],
        name=user["name"],
        email=user["email"],
        department_code=user["department_code"],
        role_code=role["code"],
        role_name=role["name"],
        clearance=role["clearance"],
        permissions=frozenset(role.get("permissions", [])),
    )

#-------------------------------------------------------------------------------------------------

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> UserContext:
    """Resolve the caller from the DB on every request, so blocking or role changes apply immediately."""

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    payload = verify_access_token(credentials.credentials)

    if not payload or not payload.get("sub"):
        raise unauthorized

    user = users_collection.find_one({"user_uuid": payload["sub"]})

    if not user:
        raise unauthorized

    if user.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is blocked",
        )

    return build_user_context(user)

#-------------------------------------------------------------------------------------------------

def require_permission(permission: str):
    """Dependency factory: allow only callers whose role grants `permission`."""

    def dependency(ctx: UserContext = Depends(get_current_user)) -> UserContext:
        if not ctx.has(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return ctx

    return dependency
