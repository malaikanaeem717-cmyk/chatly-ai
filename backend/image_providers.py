"""
Image Providers
================
Eden AI is the primary provider — an aggregator that routes to underlying
providers (Stability AI, OpenAI, Replicate, etc.) via one API and key.
Cloudflare and Hugging Face are kept as fallbacks in that order.
"""
import base64

import requests

from backend.config import settings
from backend.logging_config import logger


class EdenAIProvider:
    """Eden AI aggregator — underlying provider set via EDEN_IMAGE_PROVIDER in .env."""
    name = "edenai"
    _ENDPOINT = "https://api.edenai.run/v2/image/generation"

    def generate(self, prompt: str, width: int, height: int) -> str | None:
        if not settings.EDEN_API_KEY:
            logger.warning("Eden AI image provider skipped: EDEN_API_KEY is empty in .env.")
            return None

        headers = {"Authorization": f"Bearer {settings.EDEN_API_KEY}"}
        payload = {
            "providers": settings.EDEN_IMAGE_PROVIDER,
            "text": prompt,
            "resolution": "1024x1024",
        }

        try:
            resp = requests.post(self._ENDPOINT, headers=headers, json=payload, timeout=60)
            if resp.status_code != 200:
                logger.warning("Eden AI returned status %s: %s", resp.status_code, resp.text[:300])
                return None

            data = resp.json()
            provider_result = data.get(settings.EDEN_IMAGE_PROVIDER, {})

            if provider_result.get("status") == "fail":
                logger.warning("Eden AI provider '%s' failed: %s", settings.EDEN_IMAGE_PROVIDER, provider_result.get("error"))
                return None

            items = provider_result.get("items", [])
            if not items:
                logger.warning("Eden AI returned no image items: %s", str(data)[:300])
                return None

            item = items[0]
            b64_image = item.get("image")
            if b64_image:
                return f"data:image/png;base64,{b64_image}"

            image_url = item.get("image_resource_url")
            if image_url:
                img_resp = requests.get(image_url, timeout=30)
                if img_resp.status_code == 200:
                    return f"data:image/png;base64,{base64.b64encode(img_resp.content).decode()}"

            logger.warning("Eden AI item had no usable image data: %s", str(item)[:300])
        except Exception:
            logger.exception("Eden AI image provider failed.")
        return None


class CloudflareProvider:
    """Cloudflare Workers AI — free tier (10,000 neurons/day). Fallback provider."""
    name = "cloudflare"

    def generate(self, prompt: str, width: int, height: int) -> str | None:
        if not settings.CF_ACCOUNT_ID or not settings.CF_API_TOKEN:
            return None

        url = f"https://api.cloudflare.com/client/v4/accounts/{settings.CF_ACCOUNT_ID}/ai/run/{settings.CF_IMAGE_MODEL}"
        headers = {"Authorization": f"Bearer {settings.CF_API_TOKEN}", "Content-Type": "application/json"}

        try:
            resp = requests.post(url, headers=headers, json={"prompt": prompt}, timeout=60)
            content_type = resp.headers.get("content-type", "")

            if resp.status_code == 200 and content_type.startswith("image"):
                return f"data:image/png;base64,{base64.b64encode(resp.content).decode()}"

            if resp.status_code == 200 and content_type.startswith("application/json"):
                data = resp.json()
                b64_image = data.get("result", {}).get("image")
                if b64_image:
                    return f"data:image/png;base64,{b64_image}"
                return None

            logger.warning("Cloudflare returned status %s: %s", resp.status_code, resp.text[:300])
        except Exception:
            logger.exception("Cloudflare image provider failed.")
        return None


class HuggingFaceProvider:
    """Secondary/backup provider — HF keeps deprecating free models."""
    name = "huggingface"
    _BASE_URL = "https://router.huggingface.co/hf-inference/models"

    def generate(self, prompt: str, width: int, height: int) -> str | None:
        if not settings.HF_TOKEN:
            return None

        headers = {"Authorization": f"Bearer {settings.HF_TOKEN}"}
        for model in settings.HF_IMAGE_MODELS:
            try:
                resp = requests.post(
                    f"{self._BASE_URL}/{model}",
                    headers=headers, json={"inputs": prompt}, timeout=60,
                )
                content_type = resp.headers.get("content-type", "")
                if resp.status_code == 200 and content_type.startswith("image"):
                    return f"data:image/jpeg;base64,{base64.b64encode(resp.content).decode()}"
                logger.warning("Hugging Face model %s returned status %s: %s", model, resp.status_code, resp.text[:200])
            except Exception:
                logger.exception("Hugging Face model %s raised an exception.", model)
        return None


class GeminiImageProvider:
    """Google's Gemini image model ('Nano Banana'). Needs billing enabled."""
    name = "gemini"

    def generate(self, prompt: str, width: int, height: int) -> str | None:
        if not settings.GEMINI_API_KEY:
            return None
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            response = client.models.generate_content(
                model=settings.GEMINI_IMAGE_MODEL,
                contents=[prompt],
                config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
            )
            for candidate in response.candidates or []:
                for part in candidate.content.parts or []:
                    inline = getattr(part, "inline_data", None)
                    if inline and inline.data:
                        mime = inline.mime_type or "image/png"
                        return f"data:{mime};base64,{base64.b64encode(inline.data).decode()}"
        except Exception:
            logger.exception("Gemini (Nano Banana) image provider failed.")
        return None


PROVIDER_REGISTRY = {
    "edenai": EdenAIProvider,
    "cloudflare": CloudflareProvider,
    "huggingface": HuggingFaceProvider,
    "gemini": GeminiImageProvider,
}