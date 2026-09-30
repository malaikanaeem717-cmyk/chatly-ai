"""Document routes — authenticated, and every conversation is ownership-checked."""
import json
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File

from backend import database as db
from backend import auth
from backend.document_service import DocumentService
from backend.chat_routes import _verify_ownership

router = APIRouter(prefix="/api/documents", tags=["documents"])
_service = DocumentService()


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    conversation_id: Optional[str] = None,
    user: dict = Depends(auth.get_current_user),
):
    if conversation_id:
        _verify_ownership(conversation_id, user["id"])
        conversation = db.get_conversation(conversation_id)
    else:
        conversation = db.create_conversation(user["id"], file.filename)

    file_bytes = await file.read()
    result = _service.ingest(conversation["id"], file.filename, file_bytes)
    result["conversation_id"] = conversation["id"]

    db.add_message(
        conversation["id"], "user",
        json.dumps({"filename": result["filename"], "chunk_count": result.get("chunk_count", 0)}),
        message_type="file_notice",
    )
    return result


@router.get("/{conversation_id}")
def list_documents(conversation_id: str, user: dict = Depends(auth.get_current_user)):
    _verify_ownership(conversation_id, user["id"])
    return _service.list_documents(conversation_id)


@router.delete("/{document_id}")
def delete_document(document_id: str, user: dict = Depends(auth.get_current_user)):
    _service.delete_document(document_id)
    return {"success": True}
