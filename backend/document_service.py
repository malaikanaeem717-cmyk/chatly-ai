"""Document Service — validate -> extract -> chunk -> embed -> save to Supabase."""
from backend.exceptions import DocumentProcessingError, FileValidationError
from backend.logging_config import logger
from backend.config import settings
from backend.document_processing import extract_text
from backend.chunking import chunk_text
from backend.embeddings import embed_texts
from backend import database as db


def _validate_upload(filename: str, size_bytes: int):
    if not filename:
        raise FileValidationError("Filename is missing.")
    ext = "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise FileValidationError(f"Unsupported file type '{ext}'. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}")
    if size_bytes == 0:
        raise FileValidationError("The uploaded file is empty.")
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if size_bytes > max_bytes:
        raise FileValidationError(f"File is too large. Max allowed size is {settings.MAX_UPLOAD_MB}MB.")


class DocumentService:
    def ingest(self, conversation_id: str, filename: str, file_bytes: bytes) -> dict:
        _validate_upload(filename, len(file_bytes))
        doc = db.create_document(conversation_id, filename)

        try:
            extracted = extract_text(file_bytes, filename)
            raw_chunks = chunk_text(extracted["text"])
            if not raw_chunks:
                raise DocumentProcessingError("No usable content could be extracted from this file.")

            embeddings = embed_texts(raw_chunks)
            payload = [{"content": c, "embedding": e} for c, e in zip(raw_chunks, embeddings)]
            db.bulk_create_chunks(doc["id"], conversation_id, filename, payload)
            db.mark_document_ready(doc["id"], len(raw_chunks))

            logger.info("Document ingested: %s (%d chunks)", filename, len(raw_chunks))
            return {"success": True, "document_id": doc["id"], "filename": filename, "chunk_count": len(raw_chunks)}
        except DocumentProcessingError as exc:
            db.mark_document_failed(doc["id"], exc.message)
            return {"success": False, "document_id": doc["id"], "filename": filename, "error": exc.message}
        except Exception:
            logger.exception("Unexpected error ingesting document %s", filename)
            db.mark_document_failed(doc["id"], "Unexpected processing error.")
            return {"success": False, "document_id": doc["id"], "filename": filename, "error": "Something went wrong while processing this file."}

    def list_documents(self, conversation_id: str) -> list[dict]:
        docs = db.list_documents(conversation_id)
        return [
            {"id": d["id"], "filename": d["filename"], "status": d["status"], "chunk_count": d["chunk_count"], "error": d.get("error_message", "")}
            for d in docs
        ]

    def delete_document(self, document_id: str):
        db.delete_document(document_id)
