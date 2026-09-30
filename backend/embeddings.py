"""Local sentence embeddings (sentence-transformers) — no external API needed."""
from backend.config import settings
from backend.exceptions import EmbeddingError
from backend.logging_config import logger

_model = None


def _get_model():
    global _model
    if _model is None:
        logger.info("Loading embedding model: %s", settings.EMBEDDING_MODEL)
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    try:
        return _get_model().encode(texts, convert_to_numpy=True).tolist()
    except Exception as exc:
        logger.exception("Embedding batch failed")
        raise EmbeddingError() from exc


def embed_query(text: str) -> list[float]:
    try:
        return _get_model().encode([text], convert_to_numpy=True)[0].tolist()
    except Exception as exc:
        logger.exception("Query embedding failed")
        raise EmbeddingError() from exc
