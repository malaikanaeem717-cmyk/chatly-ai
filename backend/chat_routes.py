"""Chat routes — every endpoint requires a valid Supabase session (Bearer token)."""
from fastapi import APIRouter, Depends

from backend.models import ChatRequest, ChatResponse
from backend.chat_service import ChatService
from backend import database as db
from backend import auth
from backend.exceptions import ChatlyError, NotFoundError
from backend.logging_config import logger

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _verify_ownership(conversation_id: str, user_id: str):
    conv = db.get_conversation(conversation_id)
    if not conv or conv["user_id"] != user_id:
        raise NotFoundError("Conversation not found.")
    return conv


@router.post("", response_model=ChatResponse)
def send_message(body: ChatRequest, user: dict = Depends(auth.get_current_user)):
    try:
        if body.conversation_id:
            _verify_ownership(body.conversation_id, user["id"])
        result = ChatService().handle_message(user["id"], body.conversation_id, body.message)
        return result
    except ChatlyError as exc:
        logger.warning("Chat error: %s", exc.message)
        return ChatResponse(conversation_id=body.conversation_id or "", reply=f"⚠️ {exc.message}", sources=[], intent="error")


@router.get("/conversations")
def list_conversations(user: dict = Depends(auth.get_current_user)):
    return db.list_conversations(user["id"])


@router.get("/conversations/{conversation_id}/messages")
def get_messages(conversation_id: str, user: dict = Depends(auth.get_current_user)):
    _verify_ownership(conversation_id, user["id"])
    return db.list_messages(conversation_id)


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, user: dict = Depends(auth.get_current_user)):
    _verify_ownership(conversation_id, user["id"])
    db.delete_conversation(conversation_id)
    return {"success": True}
