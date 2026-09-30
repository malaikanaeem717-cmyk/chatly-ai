"""
Database
========
All Supabase table operations live here. Matches the tables created by
`schema.sql`: `conversations`, `messages`, `documents`, `chunks`.

If the app sits idle for a while (hours/days) and Supabase's server closes
the underlying HTTP connection in the background, the next request can
fail with "Server disconnected" even though nothing is actually wrong —
the cached client just doesn't know its connection died. `_with_retry`
catches exactly that class of error, throws away the cached client, and
retries the call once with a fresh connection — invisible to the user.
"""
import httpx
from supabase import create_client, Client

from backend.config import settings
from backend.logging_config import logger

_anon_client: Client | None = None
_admin_client: Client | None = None


def get_anon_client() -> Client:
    global _anon_client
    if _anon_client is None:
        _anon_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    return _anon_client


def get_admin_client() -> Client:
    global _admin_client
    if _admin_client is None:
        _admin_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    return _admin_client


def _reset_clients():
    global _anon_client, _admin_client
    _anon_client = None
    _admin_client = None


def _with_retry(func):
    """Retries once, with a fresh Supabase client, if the connection was stale/dropped."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadTimeout) as exc:
            logger.warning("Supabase connection dropped (%s) — resetting client and retrying once.", type(exc).__name__)
            _reset_clients()
            return func(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------- Chats (conversations)
@_with_retry
def create_conversation(user_id: str, title: str) -> dict:
    db = get_admin_client()
    res = db.table("conversations").insert({"user_id": user_id, "title": title or "New Chat"}).execute()
    return res.data[0]


@_with_retry
def get_conversation(conversation_id: str) -> dict | None:
    db = get_admin_client()
    res = db.table("conversations").select("*").eq("id", conversation_id).limit(1).execute()
    return res.data[0] if res.data else None


@_with_retry
def list_conversations(user_id: str) -> list[dict]:
    db = get_admin_client()
    res = (
        db.table("conversations")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data


@_with_retry
def delete_conversation(conversation_id: str):
    db = get_admin_client()
    db.table("conversations").delete().eq("id", conversation_id).execute()


@_with_retry
def update_conversation_summary(conversation_id: str, summary: str):
    db = get_admin_client()
    db.table("conversations").update({"summary": summary}).eq("id", conversation_id).execute()


def get_or_create_conversation(user_id: str, conversation_id: str | None, default_title: str) -> dict:
    if conversation_id:
        conv = get_conversation(conversation_id)
        if conv and conv["user_id"] == user_id:
            return conv
    return create_conversation(user_id, default_title)


# ---------------------------------------------------------------- Messages
@_with_retry
def add_message(conversation_id: str, role: str, content: str, message_type: str = "text",
                 sources: list | None = None, extra: dict | None = None) -> dict:
    db = get_admin_client()
    res = db.table("messages").insert({
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "message_type": message_type,
        "sources": sources or [],
        "extra": extra or {},
    }).execute()
    return res.data[0]


@_with_retry
def list_messages(conversation_id: str) -> list[dict]:
    db = get_admin_client()
    res = (
        db.table("messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=False)
        .execute()
    )
    return res.data


# ---------------------------------------------------------------- Documents
@_with_retry
def create_document(conversation_id: str, filename: str) -> dict:
    db = get_admin_client()
    res = db.table("documents").insert({
        "conversation_id": conversation_id, "filename": filename, "status": "processing",
    }).execute()
    return res.data[0]


@_with_retry
def mark_document_ready(document_id: str, chunk_count: int):
    db = get_admin_client()
    db.table("documents").update({"status": "ready", "chunk_count": chunk_count}).eq("id", document_id).execute()


@_with_retry
def mark_document_failed(document_id: str, error_message: str):
    db = get_admin_client()
    db.table("documents").update({"status": "failed", "error_message": error_message[:500]}).eq("id", document_id).execute()


@_with_retry
def list_documents(conversation_id: str) -> list[dict]:
    db = get_admin_client()
    res = (
        db.table("documents")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=False)
        .execute()
    )
    return res.data


@_with_retry
def delete_document(document_id: str):
    db = get_admin_client()
    db.table("documents").delete().eq("id", document_id).execute()


# ---------------------------------------------------------------- Document chunks
@_with_retry
def bulk_create_chunks(document_id: str, conversation_id: str, filename: str, chunks: list[dict]):
    db = get_admin_client()
    rows = [
        {
            "document_id": document_id,
            "conversation_id": conversation_id,
            "chunk_index": i,
            "content": c["content"],
            "embedding": c["embedding"],
            "filename": filename,
        }
        for i, c in enumerate(chunks)
    ]
    if rows:
        db.table("chunks").insert(rows).execute()


@_with_retry
def list_chunks(conversation_id: str) -> list[dict]:
    db = get_admin_client()
    res = db.table("chunks").select("*").eq("conversation_id", conversation_id).execute()
    return res.data