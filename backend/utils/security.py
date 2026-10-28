import os

from dotenv import load_dotenv
import bcrypt

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

#-------------------------------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Convert a plain password into a bcrypt hash (max 72 UTF-8 bytes)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

#-------------------------------------------------------------------------------------------------

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check whether a password matches its stored hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except (TypeError, ValueError, AttributeError):
        return False
