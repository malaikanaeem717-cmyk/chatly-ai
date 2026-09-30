"""Pydantic request/response schemas — the API's public contract."""
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)


class SignInRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class AuthResponse(BaseModel):
    success: bool
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    email: Optional[str] = None
    error: Optional[str] = None
    needs_email_confirmation: bool = False


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    sources: list = []
    intent: str = "general"
    message_type: str = "text"
    # chat_service.py's _handle_image_intent() puts the generated image data
    # here (extra={"image": ..., "provider": ...}) when a plain chat message
    # is auto-detected as an image request. This field MUST exist here —
    # without it, FastAPI's response_model silently drops "extra" from the
    # JSON response and the frontend never receives the image at all.
    extra: dict = {}


class ImageRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    style: str = "realistic"
    width: int = 1024
    height: int = 1024
    conversation_id: Optional[str] = None


class ImageResponse(BaseModel):
    success: bool
    image: Optional[str] = None
    provider: Optional[str] = None
    error: Optional[str] = None
    conversation_id: Optional[str] = None