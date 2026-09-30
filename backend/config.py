"""
Configuration
=============
Reads every setting from environment variables (.env file). No other file
should call os.getenv() directly — everything goes through `settings`.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool(name, default):
    v = os.getenv(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


def _int(name, default):
    v = os.getenv(name)
    try:
        return int(v) if v is not None else default
    except ValueError:
        return default


def _float(name, default):
    v = os.getenv(name)
    try:
        return float(v) if v is not None else default
    except ValueError:
        return default


class Settings:
    APP_NAME = "Chatly AI"
    ENV = os.getenv("ENV", "development")
    DEBUG = _bool("DEBUG", True)

    # --- Supabase ---
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

    # --- LLM ---
    LLM_PROVIDERS = [p.strip().lower() for p in os.getenv("LLM_PROVIDERS", "groq,gemini").split(",") if p.strip()]
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").strip().lower()  # "groq" or "gemini"

    # --- Groq ---
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    GROQ_SUMMARY_MODEL = os.getenv("GROQ_SUMMARY_MODEL", "llama-3.1-8b-instant")

    # --- Gemini (chat + image) ---
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
    GEMINI_SUMMARY_MODEL = os.getenv("GEMINI_SUMMARY_MODEL", "gemini-flash-latest")
    GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")

    # --- Embeddings ---
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    # --- Chunking ---
    CHUNK_SIZE = _int("CHUNK_SIZE", 900)
    CHUNK_OVERLAP = _int("CHUNK_OVERLAP", 150)

    # --- Retrieval ---
    RETRIEVAL_TOP_K = _int("RETRIEVAL_TOP_K", 8)
    RERANK_TOP_K = _int("RERANK_TOP_K", 4)
    RELEVANCE_THRESHOLD = _float("RELEVANCE_THRESHOLD", 0.28)
    SEMANTIC_WEIGHT = _float("SEMANTIC_WEIGHT", 0.65)
    LEXICAL_WEIGHT = _float("LEXICAL_WEIGHT", 0.35)
    RERANK_ENABLED = _bool("RERANK_ENABLED", True)
    RERANKER_MODEL = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

    # --- Memory ---
    MEMORY_RECENT_TURNS = _int("MEMORY_RECENT_TURNS", 12)
    MEMORY_SUMMARY_TRIGGER = _int("MEMORY_SUMMARY_TRIGGER", 20)
    # ---Extension----
    ALLOWED_EXTENSIONS = (".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg", ".webp")
    # --- Images ---
        # --- Images ---
       # --- Images ---
    IMAGE_PROVIDERS = [p.strip() for p in os.getenv("IMAGE_PROVIDERS", "gemini").split(",") if p.strip()]
    HF_TOKEN = os.getenv("HF_TOKEN", "")
    HF_IMAGE_MODELS = [m.strip() for m in os.getenv("HF_IMAGE_MODELS", "black-forest-labs/FLUX.1-schnell").split(",") if m.strip()]
    CF_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID", "")
    CF_API_TOKEN = os.getenv("CF_API_TOKEN", "")
    CF_IMAGE_MODEL = os.getenv("CF_IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell")
    IMAGE_DEFAULT_WIDTH = _int("IMAGE_DEFAULT_WIDTH", 1024)
    IMAGE_DEFAULT_HEIGHT = _int("IMAGE_DEFAULT_HEIGHT", 1024)
    EDEN_API_KEY = os.getenv("EDEN_API_KEY", "")
    EDEN_IMAGE_PROVIDER = os.getenv("EDEN_IMAGE_PROVIDER", "stabilityai")
    # --- Uploads ---
    MAX_UPLOAD_MB = _int("MAX_UPLOAD_MB", 20)
    ALLOWED_EXTENSIONS = (".pdf", ".docx", ".txt")

    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")]


settings = Settings()
