"""
auth.py
=======
JWT authentication utilities for MortgageGuard AI.
Auth is OPTIONAL (non-breaking): if no token is provided, falls through
to an anonymous default user so all existing tests continue to pass.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.app.core.config import settings

# ---------------------------------------------------------------------------
# OAuth2 scheme — auto_error=False makes the token optional
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)

# ---------------------------------------------------------------------------
# Password hashing context (bcrypt)
# ---------------------------------------------------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


# ---------------------------------------------------------------------------
# Core token helpers
# ---------------------------------------------------------------------------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a signed JWT access token.

    Parameters
    ----------
    data:
        Payload dict to encode (e.g. ``{"sub": "analyst", "role": "analyst"}``).
    expires_delta:
        How long the token should be valid.  Falls back to
        ``settings.ACCESS_TOKEN_EXPIRE_MINUTES`` when omitted.

    Returns
    -------
    str
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    """
    Decode and validate a JWT token.

    Parameters
    ----------
    token:
        Raw JWT string.

    Returns
    -------
    dict
        Decoded payload.

    Raises
    ------
    HTTPException 401
        When the token is missing, expired, or invalid.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ---------------------------------------------------------------------------
# FastAPI dependency — optional auth (non-breaking)
# ---------------------------------------------------------------------------

def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> str:
    """
    Return the username embedded in the JWT token.

    If *no* token is supplied the request is treated as coming from the
    built-in ``anonymous`` user so that all unauthenticated routes and
    existing tests continue to work without modification.
    """
    if token is None:
        return "anonymous"
    payload = verify_token(token)
    username: Optional[str] = payload.get("sub")
    if username is None:
        return "anonymous"
    return username


def get_current_analyst(current_user: str = Depends(get_current_user)) -> str:
    """
    Dependency alias for analyst-level access (read + submit).

    Analysts are any authenticated user; anonymous access is also permitted
    to keep the API non-breaking.
    """
    return current_user


def get_current_reviewer(current_user: str = Depends(get_current_user)) -> str:
    """
    Dependency alias for reviewer-level access (approve / reject).

    In the current non-breaking mode all users (including anonymous) are
    accepted.  Tighten this once role-based enforcement is required.
    """
    return current_user
