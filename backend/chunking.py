"""Intelligent chunking — splits on paragraph/sentence boundaries where possible."""
import re

from backend.config import settings

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def chunk_text(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    chunk_size = chunk_size or settings.CHUNK_SIZE
    overlap = overlap or settings.CHUNK_OVERLAP

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()] or [text]
    raw_chunks: list[str] = []
    buffer = ""

    for para in paragraphs:
        sentences = _SENTENCE_SPLIT.split(para) if len(para) > chunk_size else [para]
        for sentence in sentences:
            if len(buffer) + len(sentence) + 1 <= chunk_size:
                buffer = f"{buffer} {sentence}".strip()
            else:
                if buffer:
                    raw_chunks.append(buffer)
                if len(sentence) > chunk_size:
                    raw_chunks.extend(_hard_split(sentence, chunk_size, overlap))
                    buffer = ""
                else:
                    buffer = sentence
    if buffer:
        raw_chunks.append(buffer)

    overlapped = []
    for i, c in enumerate(raw_chunks):
        if i == 0 or overlap == 0:
            overlapped.append(c)
        else:
            overlapped.append((raw_chunks[i - 1][-overlap:] + " " + c).strip())
    return [c for c in overlapped if c.strip()]


def _hard_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks
