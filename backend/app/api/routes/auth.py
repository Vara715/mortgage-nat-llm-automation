"""
auth.py  (routes)
=================
Authentication endpoints for MortgageGuard AI.

Provides:
- POST /api/auth/token  — issue a JWT for dev users
- GET  /api/auth/me     — return current user info (requires token)

Dev users are hardcoded for simplicity and reliability; no DB write is
performed so the endpoint works even on a fresh database.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from backend.app.core.auth import create_access_token, get_current_user, verify_token, oauth2_scheme

router = APIRouter(tags=["auth"])

# ---------------------------------------------------------------------------
# Hard-coded dev users: {username: {password, role}}
# ---------------------------------------------------------------------------
_DEV_USERS: dict[str, dict] = {
    "analyst":  {"password": "analyst123",  "role": "analyst"},
    "reviewer": {"password": "reviewer123", "role": "reviewer"},
    "admin":    {"password": "admin123",    "role": "admin"},
}


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class MeResponse(BaseModel):
    username: str
    role: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/auth/token", response_model=TokenResponse, summary="Obtain a JWT access token")
def login(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    """
    Exchange username + password for a JWT access token.

    Dev credentials
    ---------------
    - analyst / analyst123
    - reviewer / reviewer123
    - admin / admin123
    """
    user = _DEV_USERS.get(form_data.username)
    if user is None or user["password"] != form_data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        data={"sub": form_data.username, "role": user["role"]}
    )
    return TokenResponse(access_token=token, token_type="bearer", role=user["role"])


@router.get("/auth/me", response_model=MeResponse, summary="Return current user info")
def me(
    token: str = Depends(oauth2_scheme),
    current_user: str = Depends(get_current_user),
) -> MeResponse:
    """
    Return the username and role for the currently authenticated user.
    A valid Bearer token is required.
    """
    if token is None or current_user == "anonymous":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(token)
    role: str = payload.get("role", "analyst")
    return MeResponse(username=current_user, role=role)
