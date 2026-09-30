"""
Authentication
==============
This is the Python code that actually performs authentication — the
frontend never talks to Supabase directly. It calls these endpoints, which
use the official `supabase-py` client:

  sign_up()       -> supabase.auth.sign_up({...})
  sign_in()       -> supabase.auth.sign_in_with_password({...})
  refresh()       -> supabase.auth.refresh_session(refresh_token)
  get_current_user() -> supabase.auth.get_user(token)

Flow: on login, Supabase returns an access token (short-lived, ~1 hour)
AND a refresh token (long-lived). The frontend stores both. When the
access token expires, the frontend calls /api/auth/refresh with the
refresh token to get a new access token silently — the user is never
logged out just because time passed, only if the refresh token itself is
invalid/revoked (e.g. password changed, or refresh token very old).
"""
from fastapi import Header

from backend.database import get_anon_client
from backend.exceptions import AuthError
from backend.logging_config import logger


def sign_up(email: str, password: str) -> dict:
    try:
        result = get_anon_client().auth.sign_up({"email": email, "password": password})
    except Exception as exc:
        logger.warning("Sign up failed for %s", email)
        raise AuthError(_clean_message(exc)) from exc

    if not result.user:
        raise AuthError("Could not create account. Please try again.")

    session = result.session
    return {
        "user": {"id": result.user.id, "email": result.user.email},
        "access_token": session.access_token if session else None,
        "refresh_token": session.refresh_token if session else None,
        "needs_email_confirmation": session is None,
    }


def sign_in(email: str, password: str) -> dict:
    try:
        result = get_anon_client().auth.sign_in_with_password({"email": email, "password": password})
    except Exception as exc:
        logger.warning("Sign in failed for %s", email)
        raise AuthError("Incorrect email or password.") from exc

    if not result.session:
        raise AuthError("Incorrect email or password.")

    return {
        "user": {"id": result.user.id, "email": result.user.email},
        "access_token": result.session.access_token,
        "refresh_token": result.session.refresh_token,
    }


def refresh(refresh_token: str) -> dict:
    """Silently exchanges a refresh token for a new access token — no password needed."""
    try:
        result = get_anon_client().auth.refresh_session(refresh_token)
    except Exception as exc:
        logger.warning("Token refresh failed")
        raise AuthError("Your session has fully expired. Please log in again.") from exc

    if not result or not result.session:
        raise AuthError("Your session has fully expired. Please log in again.")

    return {
        "access_token": result.session.access_token,
        "refresh_token": result.session.refresh_token,
        "email": result.user.email if result.user else None,
    }


def get_current_user(authorization: str = Header(...)) -> dict:
    """FastAPI dependency — every protected route requires this."""
    if not authorization.startswith("Bearer "):
        raise AuthError("Missing or malformed Authorization header.")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        result = get_anon_client().auth.get_user(token)
    except Exception as exc:
        raise AuthError("Your session has expired. Please log in again.") from exc

    if not result or not result.user:
        raise AuthError("Your session has expired. Please log in again.")

    return {"id": result.user.id, "email": result.user.email}


def _clean_message(exc: Exception) -> str:
    text = str(exc)
    if "already registered" in text.lower() or "already exists" in text.lower():
        return "An account with this email already exists. Try logging in instead."
    if "password" in text.lower() and "least" in text.lower():
        return "Password is too short. Use at least 6 characters."
    return "Could not create account. Please check your details and try again."