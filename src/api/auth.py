"""
Authentication and Authorization Module for ATM Cash Demand Predictor.

Implements:
1. OAuth2 Password Bearer flow.
2. JSON Web Token (JWT) encoding and decoding with python-jose.
3. Secure password hashing directly with bcrypt (production-grade & Python 3.13 compliant).
4. Role-Based Access Control (RBAC): Admin, Operations Manager, Analyst.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from src.api.schemas import TokenData, UserProfile

# Security Configurations
SECRET_KEY = "atm-cash-demand-predictor-secret-key-production-grade"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def get_password_hash(password: str) -> str:
    """Hash password using bcrypt."""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=10)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


# Seed Users with Roles (Matching Synopsis Section 2.4)
# Default password for all seed accounts is "password123" (also supports username+"123")
_DEFAULT_HASH = get_password_hash("password123")

MOCK_USERS_DB = {
    "admin": {
        "username": "admin",
        "full_name": "Operations Director",
        "email": "director@tinkoff.ru",
        "hashed_password": _DEFAULT_HASH,
        "role": "admin",
        "is_active": True,
    },
    "manager": {
        "username": "manager",
        "full_name": "CIT Operations Manager",
        "email": "operations@tinkoff.ru",
        "hashed_password": _DEFAULT_HASH,
        "role": "operations_manager",
        "is_active": True,
    },
    "operator": {
        "username": "operator",
        "full_name": "CIT Operations Operator",
        "email": "operator@tinkoff.ru",
        "hashed_password": _DEFAULT_HASH,
        "role": "operations_manager",
        "is_active": True,
    },
    "analyst": {
        "username": "analyst",
        "full_name": "Cash Forecasting Analyst",
        "email": "analyst@tinkoff.ru",
        "hashed_password": _DEFAULT_HASH,
        "role": "analyst",
        "is_active": True,
    },
}


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Encode JWT token with expiry."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate username and password against user repository."""
    user = MOCK_USERS_DB.get(username)
    if not user:
        return None
    # Support both password123 and {username}123
    if not (verify_password(password, user["hashed_password"]) or password == f"{username}123"):
        return None
    return user


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserProfile:
    """FastAPI Dependency: Extract, decode, and validate current user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or token expired",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username, role=role)
    except JWTError:
        raise credentials_exception

    user = MOCK_USERS_DB.get(token_data.username)
    if user is None:
        raise credentials_exception

    return UserProfile(
        username=user["username"],
        full_name=user["full_name"],
        email=user["email"],
        role=user["role"],
        is_active=user["is_active"],
    )


def require_role(allowed_roles: list):
    """RBAC Dependency generator ensuring user has sufficient privileges."""
    def role_checker(current_user: UserProfile = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required roles: {allowed_roles}",
            )
        return current_user
    return role_checker
