"""Document Processing — file bytes -> clean plain text (PDF, DOCX, TXT)."""
import io
import re

from pypdf import PdfReader
from docx import Document as DocxDocument

from backend.exceptions import DocumentProcessingError
from backend.logging_config import logger


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text(file_bytes: bytes, filename: str) -> dict:
    ext = filename.lower().rsplit(".", 1)[-1]
    try:
        if ext == "pdf":
            text, page_count = _extract_pdf(file_bytes)
        elif ext == "docx":
            text, page_count = _extract_docx(file_bytes), None
        elif ext == "txt":
            text, page_count = file_bytes.decode("utf-8", errors="ignore"), None
        else:
            raise DocumentProcessingError(f"Unsupported file type: .{ext}")
    except DocumentProcessingError:
        raise
    except Exception as exc:
        logger.exception("Text extraction failed for %s", filename)
        raise DocumentProcessingError(f"Could not read '{filename}'. The file may be corrupted.") from exc

    cleaned = clean_text(text)
    if not cleaned:
        raise DocumentProcessingError(f"No readable text was found in '{filename}'.")

    return {"text": cleaned, "page_count": page_count, "word_count": len(cleaned.split())}


def _extract_pdf(file_bytes: bytes):
    reader = PdfReader(io.BytesIO(file_bytes))
    parts = [p.extract_text() for p in reader.pages if p.extract_text()]
    return "\n".join(parts), len(reader.pages)


def _extract_docx(file_bytes: bytes) -> str:
    doc = DocxDocument(io.BytesIO(file_bytes))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                parts.append(row_text)
    return "\n".join(parts)
def extract_text(file_bytes: bytes, filename: str) -> dict:
    ext = filename.lower().rsplit(".", 1)[-1]
    try:
        if ext == "pdf":
            text, page_count = _extract_pdf(file_bytes)
        elif ext == "docx":
            text, page_count = _extract_docx(file_bytes), None
        elif ext == "txt":
            text, page_count = file_bytes.decode("utf-8", errors="ignore"), None
        elif ext in ("png", "jpg", "jpeg", "webp"):
            text, page_count = _extract_image(file_bytes, ext), None
        else:
            raise DocumentProcessingError(f"Unsupported file type: .{ext}")
    except DocumentProcessingError:
        raise
    except Exception as exc:
        logger.exception("Text extraction failed for %s", filename)
        raise DocumentProcessingError(f"Could not read '{filename}'. The file may be corrupted.") from exc

    cleaned = clean_text(text)
    if not cleaned:
        raise DocumentProcessingError(f"No readable text was found in '{filename}'.")

    return {"text": cleaned, "page_count": page_count, "word_count": len(cleaned.split())}
def _extract_image(file_bytes: bytes, ext: str) -> str:
    """Uses Gemini's vision capability to describe an image and transcribe any visible text."""
    from google import genai
    from google.genai import types
    from backend.config import settings
    from backend.exceptions import DocumentProcessingError as _Err

    if not settings.GEMINI_API_KEY:
        raise _Err("Image analysis requires GEMINI_API_KEY to be configured in .env.")

    mime = f"image/{'jpeg' if ext == 'jpg' else ext}"
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=file_bytes, mime_type=mime),
            "Describe this image in detail, and transcribe any visible text exactly as written, "
            "in whatever language it appears in. Be thorough and factual.",
        ],
    )
    return getattr(response, "text", "") or ""