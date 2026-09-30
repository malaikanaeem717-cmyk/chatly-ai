"""Intent detection — fast rule-based patterns first, LLM fallback for anything the
patterns miss (e.g. Roman Urdu/Hindi or phrasing without an English keyword)."""
import re

from backend.logging_config import logger

_IMAGE_PATTERNS = [
    r"\bgenerate (an? )?image\b", r"\bcreate (an? )?image\b", r"\bdraw\b",
    r"\bmake (an? )?(image|picture|photo)\b", r"\bimage of\b", r"\bpicture of\b",
    r"\bphoto of\b", r"\billustrat", r"\brender (an? )?image\b",
    # Roman Urdu / Hindi common phrasings
    r"\btasveer\b", r"\btasvir\b", r"\bimage ban", r"\bpic ban", r"\bphoto ban",
    r"\btasveer ban", r"\btasvir ban", r"\bimage bnado\b", r"\bpic bnado\b",
]
_SUMMARY_PATTERNS = [r"\bsummar", r"\bin short\b", r"\btl;?dr\b", r"\bkey points\b"]
_COMPARISON_PATTERNS = [r"\bcompare\b", r"\bdifference between\b", r"\bversus\b", r"\bvs\.?\b"]
_FOLLOWUP_PRONOUNS = [r"\bit\b", r"\bthis\b", r"\bthat\b", r"\bthey\b", r"\bthem\b", r"\bthose\b"]
_QUESTION_STARTERS = ("what", "why", "how", "who", "when", "where", "which", "is", "are", "does", "do", "can", "explain", "tell")

_INTENT_CHECK_INSTRUCTION = (
    "Reply with exactly one word: YES or NO. Question: Is the following message a request "
    "asking to generate, create, draw, or make an image/picture/photo — in ANY language or "
    "script (English, Roman Urdu, Hindi, Arabic script, etc.)? Message:"
)


def _regex_is_image_request(text: str) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in _IMAGE_PATTERNS)


def _llm_is_image_request(text: str) -> bool:
    """Fallback for phrasing the regex patterns don't cover — asks the LLM directly."""
    try:
        from backend.llm_provider import get_llm_provider
        llm = get_llm_provider()
        answer = llm.invoke_text(f"{_INTENT_CHECK_INSTRUCTION} \"{text}\"")
        return answer.strip().upper().startswith("YES")
    except Exception:
        logger.warning("LLM-based image-intent fallback check failed — assuming not an image request.")
        return False


def is_image_request(text: str) -> bool:
    if _regex_is_image_request(text):
        return True
    return _llm_is_image_request(text)


def classify_intent(text: str, has_history: bool) -> dict:
    t = text.lower().strip()
    words = t.split()

    if is_image_request(t):
        intent = "image_generation"
    elif any(re.search(p, t) for p in _SUMMARY_PATTERNS):
        intent = "summary_request"
    elif any(re.search(p, t) for p in _COMPARISON_PATTERNS):
        intent = "comparison"
    elif has_history and len(words) <= 6 and any(re.search(p, t) for p in _FOLLOWUP_PRONOUNS):
        intent = "follow_up"
    elif t.endswith("?") or (words and words[0] in _QUESTION_STARTERS):
        intent = "question"
    else:
        intent = "general"

    return {"intent": intent, "is_image_request": intent == "image_generation"}