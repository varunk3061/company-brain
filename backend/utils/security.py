import os

from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from jose import jwt, JWTError
from passlib.context import CryptContext

#-------------------------------------------------------------------------------------------------

load_dotenv()

#-------------------------------------------------------------------------------------------------

# Support the existing .env variable names
SECRET_KEY = (
    os.getenv("jwt_secret_key") 
    or os.getenv("JWT_SECRET_KEY")
)

ALGORITHM = (
    os.getenv("jwt_algorithm")
    or os.getenv("JWT_ALGORITHM")
    or "HS256"
)

ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("access_token_expire_minutes")
    or os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")
    or "60"
)

if not SECRET_KEY:
    raise ValueError("JWT secret key is missing from .env")

if len(SECRET_KEY) < 32:
    raise ValueError("JWT secret key must be at least 32 characters")

if ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
    raise ValueError("Token expiration must be greater than zero")

# Password hashing configuration
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

#-------------------------------------------------------------------------------------------------

def hash_password(password:str):
    """Covert a plain password into a secure hash"""
    return pwd_context.hash(password)

#-------------------------------------------------------------------------------------------------

def verify_password( plain_password: str, hashed_password: str ):
    """Check whether a password matches its stored hash"""
    try:
        return pwd_context.verify(
            plain_password, hashed_password
        )
    except (TypeError, ValueError):
        return False

#-------------------------------------------------------------------------------------------------

def create_access_token(data):
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )