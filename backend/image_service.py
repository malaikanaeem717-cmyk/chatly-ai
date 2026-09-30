"""
Image generation orchestration.
"""
import re

from backend.config import settings
from backend.exceptions import ImageGenerationError
from backend.logging_config import logger
from backend.image_providers import PROVIDER_REGISTRY
from backend.llm_provider import get_llm_provider
from langchain_core.messages import SystemMessage, HumanMessage

_GENERAL_QUALITY = {
    "realistic": "photorealistic, ultra detailed, high resolution, professional photography, sharp focus, natural lighting, no text, no watermark, no logo, no signature",
    "artistic": "digital painting, artstation trending, dramatic lighting, high detail, no text, no watermark",
    "anime": "anime style, studio quality, vibrant colors, clean line art, no text, no watermark",
    "3d": "3d render, octane render, cinematic lighting, high detail, physically based rendering, no text, no watermark",
}

_PROMPT_REWRITE_INSTRUCTION = (
    "You turn a user's image request (in any language) into a single, clean, English "
    "image-generation prompt for a text-to-image AI model. Rules:\n"
    "- Describe ONLY what the user actually asked for — do not add unrelated subjects.\n"
    "- If the request involves a person/people, add natural, realistic descriptors relevant "
    "to that (skin texture, natural proportions, natural expression) — but never add these "
    "if there is no person in the request (e.g. a car, a landscape, an object, an animal).\n"
    "- Keep it concise: one comma-separated line, no explanations, no quotes, no extra text.\n"
    "- Output ONLY the final prompt, nothing else."
)

# Explicit size like "1200x628" or "1080 x 1920" typed anywhere in the request.
_DIMENSION_PATTERN = re.compile(r"\b(\d{2,4})\s*[x\u00d7]\s*(\d{2,4})\b")
_BANNER_KEYWORDS = re.compile(r"\b(banner|cover photo|cover image|header image|web banner|website banner)\b", re.IGNORECASE)

_MIN_DIM, _MAX_DIM = 256, 2048
_DEFAULT_BANNER_SIZE = (1600, 500)  # wide, responsive-friendly ratio; scales down via CSS on the frontend


def determine_dimensions(prompt: str, requested_width: int, requested_height: int) -> tuple[int, int]:
    """
    Precedence: an explicit "WxH" the user typed > a detected 'banner'-style
    request (uses a wide default) > whatever width/height was already passed in.
    """
    match = _DIMENSION_PATTERN.search(prompt)
    if match:
        w = max(_MIN_DIM, min(int(match.group(1)), _MAX_DIM))
        h = max(_MIN_DIM, min(int(match.group(2)), _MAX_DIM))
        return w, h

    if _BANNER_KEYWORDS.search(prompt):
        return _DEFAULT_BANNER_SIZE

    return requested_width, requested_height


def _rewrite_prompt_with_llm(raw_prompt: str) -> str:
    try:
        llm = get_llm_provider()
        result = llm.invoke_messages([
            SystemMessage(content=_PROMPT_REWRITE_INSTRUCTION),
            HumanMessage(content=raw_prompt),
        ])
        cleaned = result.strip().strip('"')
        return cleaned if cleaned else raw_prompt
    except Exception:
        logger.warning("Prompt rewrite via LLM failed — using the raw prompt instead.")
        return raw_prompt


def enhance_prompt(prompt: str, style: str) -> str:
    rewritten = _rewrite_prompt_with_llm(prompt.strip())
    quality = _GENERAL_QUALITY.get(style, _GENERAL_QUALITY["realistic"])
    return f"{rewritten}, {quality}"


class ImageGenerationService:
    def __init__(self):
        configured = settings.IMAGE_PROVIDERS
        self.providers = [PROVIDER_REGISTRY[n]() for n in configured if n in PROVIDER_REGISTRY]

        unknown = [n for n in configured if n not in PROVIDER_REGISTRY]
        if unknown:
            logger.warning(
                "IMAGE_PROVIDERS in .env lists unknown provider(s) %s — skipped. Valid options: %s",
                unknown, list(PROVIDER_REGISTRY.keys()),
            )
        if not self.providers:
            logger.error("No valid image providers are configured! Image generation will always fail until this is fixed.")
        else:
            logger.info("Image generation providers active, in order: %s", [p.name for p in self.providers])

    def generate(self, prompt: str, style: str, width: int, height: int) -> dict:
        if not prompt.strip():
            raise ImageGenerationError("Prompt cannot be empty.")
        if not self.providers:
            raise ImageGenerationError("No image provider is configured on the server. Check IMAGE_PROVIDERS in .env.")

        width, height = determine_dimensions(prompt, width, height)
        enhanced = enhance_prompt(prompt, style)
        logger.info("Enhanced image prompt: %s | size: %sx%s", enhanced, width, height)

        for provider in self.providers:
            image_data = provider.generate(enhanced, width, height)
            if image_data:
                return {"image": image_data, "provider": provider.name}
            logger.info("Provider %s returned nothing, trying next.", provider.name)

        raise ImageGenerationError("Image generation is temporarily unavailable. Please try again shortly.")