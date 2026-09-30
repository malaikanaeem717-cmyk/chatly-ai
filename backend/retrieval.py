"""
Retrieval
=========
Hybrid search (semantic + BM25 keyword) fused with configurable weights,
then optional cross-encoder reranking, then citation building. One file
because these three steps are always used together as a single pipeline.
"""
import re
import numpy as np
from rank_bm25 import BM25Okapi

from backend.config import settings
from backend.logging_config import logger

# ---------------------------------------------------------------- Semantic
def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


# ---------------------------------------------------------------- Lexical (BM25)
def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _bm25_scores(query: str, documents: list[str]) -> list[float]:
    if not documents:
        return []
    bm25 = BM25Okapi([_tokenize(d) for d in documents])
    return list(bm25.get_scores(_tokenize(query)))


def _normalize(scores: list[float]) -> list[float]:
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi - lo < 1e-9:
        return [0.0 for _ in scores]
    return [(s - lo) / (hi - lo) for s in scores]


# ---------------------------------------------------------------- Hybrid fusion
def hybrid_retrieve(query: str, query_embedding: list[float], chunks: list[dict], top_k: int | None = None) -> list[dict]:
    """chunks: [{"content", "embedding", "filename", "chunk_index"}, ...]"""
    top_k = top_k or settings.RETRIEVAL_TOP_K
    if not chunks:
        return []

    sem_raw = [cosine_similarity(query_embedding, c["embedding"]) for c in chunks]
    lex_raw = _bm25_scores(query, [c["content"] for c in chunks])
    sem_norm, lex_norm = _normalize(sem_raw), _normalize(lex_raw)

    candidates = []
    for i, c in enumerate(chunks):
        fused = settings.SEMANTIC_WEIGHT * sem_norm[i] + settings.LEXICAL_WEIGHT * lex_norm[i]
        candidates.append({**c, "semantic_score": sem_raw[i], "lexical_score": lex_raw[i], "score": fused})

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:top_k]


# ---------------------------------------------------------------- Reranking
_cross_encoder = None
_load_failed = False


def _get_cross_encoder():
    global _cross_encoder, _load_failed
    if _load_failed:
        return None
    if _cross_encoder is None:
        try:
            from sentence_transformers import CrossEncoder
            _cross_encoder = CrossEncoder(settings.RERANKER_MODEL)
        except Exception:
            logger.warning("Reranker model could not be loaded — falling back to hybrid ranking only.")
            _load_failed = True
            return None
    return _cross_encoder


def _dedupe(candidates: list[dict]) -> list[dict]:
    seen, unique = set(), []
    for c in candidates:
        key = c["content"][:120]
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def rerank(query: str, candidates: list[dict], top_k: int | None = None) -> list[dict]:
    top_k = top_k or settings.RERANK_TOP_K
    if not candidates:
        return []
    if not settings.RERANK_ENABLED:
        return _dedupe(candidates)[:top_k]

    encoder = _get_cross_encoder()
    if encoder is None:
        return _dedupe(candidates)[:top_k]

    try:
        scores = encoder.predict([(query, c["content"]) for c in candidates])
    except Exception:
        logger.warning("Reranking failed at inference time — falling back to hybrid ranking.")
        return _dedupe(candidates)[:top_k]

    for c, s in zip(candidates, scores):
        c["rerank_score"] = float(s)
    candidates.sort(key=lambda x: x.get("rerank_score", x["score"]), reverse=True)
    return _dedupe(candidates)[:top_k]


# ---------------------------------------------------------------- Citations
def build_citations(used_chunks: list[dict]) -> list[dict]:
    citations, seen = [], set()
    for c in used_chunks:
        key = (c["filename"], c["chunk_index"])
        if key in seen:
            continue
        seen.add(key)
        citations.append({
            "document": c["filename"],
            "section": c["chunk_index"] + 1,
            "relevance": round(c.get("rerank_score", c.get("score", 0.0)), 3),
        })
    return citations
