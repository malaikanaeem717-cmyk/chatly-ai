"""Auth routes — thin HTTP layer over backend/auth.py."""
from fastapi import APIRouter, Depends

from backend.models import SignUpRequest, SignInRequest, RefreshRequest, AuthResponse
from backend import auth
from backend.exceptions import AuthError

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse)
def signup(body: SignUpRequest):
    try:
        result = auth.sign_up(body.email, body.password)
        return AuthResponse(
            success=True,
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            email=result["user"]["email"],
            needs_email_confirmation=result["needs_email_confirmation"],
        )
    except AuthError as exc:
        return AuthResponse(success=False, error=exc.message)


@router.post("/login", response_model=AuthResponse)
def login(body: SignInRequest):
    try:
        result = auth.sign_in(body.email, body.password)
        return AuthResponse(
            success=True,
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            email=result["user"]["email"],
        )
    except AuthError as exc:
        return AuthResponse(success=False, error=exc.message)


@router.post("/refresh", response_model=AuthResponse)
def refresh(body: RefreshRequest):
    """Called silently by the frontend when the access token expires — no password needed."""
    try:
        result = auth.refresh(body.refresh_token)
        return AuthResponse(
            success=True,
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            email=result["email"],
        )
    except AuthError as exc:
        return AuthResponse(success=False, error=exc.message)


@router.get("/me")
def me(user: dict = Depends(auth.get_current_user)):
    return {"id": user["id"], "email": user["email"]}