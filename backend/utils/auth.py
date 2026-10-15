import os

from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from database.connection import admins_collection, employees_collection
from utils.security import (
    SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, verify_password
)

#-------------------------------------------------------------------------------------------------

load_dotenv()

bearer_scheme = HTTPBearer(auto_error=False)

#-------------------------------------------------------------------------------------------------

def create_access_token(admin:dict) -> str:
    """Create a signed JWT for an authenticate admin"""

    now = datetime.now(timezone.utc)

    payload = {
        "sub" : admin["email"],
        "admin_uuid" : admin["admin_uuid"],
        "role" : "admin",
        "iat" : now,
        "exp" : now + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        ),
    }

    return jwt.encode(
        payload, SECRET_KEY, algorithm=ALGORITHM
    )

#-------------------------------------------------------------------------------------------------

def verify_access_token(token:str) :
    """Decode a token or return None if it is invalid."""

    try:
        return jwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM]
        )
    except JWTError:
        return None

#-------------------------------------------------------------------------------------------------

def get_current_admin( credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme) ) -> dict:
    """Allow access only to a valid, existing admin"""

    unauthorized_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"www-Authenticate" : "Bearer"}
    )

    if credentials is None:
        raise unauthorized_error

    payload = verify_access_token(credentials.credentials)

    if payload is None:
        raise unauthorized_error

    if payload.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    admin_uuid = payload.get("admin_uuid")
    email = payload.get("sub")

    if not admin_uuid or not email:
        raise unauthorized_error

    # Check that the admin still exists in MongoDB.
    admin = admins_collection.find_one({
        "admin_uuid" : admin_uuid,
        "email" : email,
    })

    if not admin:
        raise unauthorized_error

    return admin

#-------------------------------------------------------------------------------------------------

def create_employee_access_token(employee: dict) -> str:
    """Create a JWT for an employee."""

    now = datetime.now(timezone.utc)

    payload = {
        "sub" : employee["email"],
        "employee_uuid" : employee["employee_uuid"],
        "role" : "employee",
        "iat" : now,
        "exp" : now + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        ),
    }

    return jwt.encode(
        payload, SECRET_KEY, algorithm=ALGORITHM
    )

#-------------------------------------------------------------------------------------------------

def get_current_employee(credentials : HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict :
    """Allow only active employee with valid tokens"""

    unauthorized_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or Expired authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized_error

    payload =verify_access_token(credentials.credentials)

    if not payload:
        raise unauthorized_error

    if payload.get("role") != "employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee access required."
        )

    employee_uuid = payload.get("employee_uuid")
    email = payload.get("sub")

    if not employee_uuid or not email:
        raise unauthorized_error

    employee = employees_collection.find_one({
        "employee_uuid" : employee_uuid,
        "email" : email,
    })

    if not employee:
        raise unauthorized_error

    if employee.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your Employee Account is Blocked",
        )
    
    return employee