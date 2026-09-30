"""
LLM Provider — tries providers in order (LLM_PROVIDERS in .env, default
"groq,gemini"). If the first one fails or errors out, it automatically
falls through to the next one in the SAME request — the user never sees
an error unless every provider in the list fails.
"""
import time
import requests

from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from backend.config import settings
from backend.exceptions import LLMProviderError
from backend.logging_config import logger

_MAX_ATTEMPTS = 2
_RETRY_DELAY_SECONDS = 1


def _messages_to_openai_format(messages: list) -> list[dict]:
    formatted = []
    for m in messages:
        if isinstance(m, SystemMessage):
            formatted.append({"role": "system", "content": m.content})
        elif isinstance(m, HumanMessage):
            formatted.append({"role": "user", "content": m.content})
        elif isinstance(m, AIMessage):
            formatted.append({"role": "assistant", "content": m.content})
    return formatted


class GroqProvider:
    """Groq's OpenAI-compatible chat completions API — typically 1-3s responses."""
    name = "groq"
    _ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, model: str | None = None):
        self._model = model or settings.GROQ_MODEL

    def invoke_messages(self, messages: list) -> str:
        if not settings.GROQ_API_KEY:
            raise LLMProviderError("GROQ_API_KEY is not configured.")

        payload = {"model": self._model, "messages": _messages_to_openai_format(messages), "temperature": 0.7}
        headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}", "Content-Type": "application/json"}

        last_exc = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                resp = requests.post(self._ENDPOINT, headers=headers, json=payload, timeout=20)
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]
                if resp.status_code in (429, 503):
                    last_exc = Exception(f"Groq {resp.status_code}")
                    logger.warning("Groq busy (attempt %s/%s)", attempt, _MAX_ATTEMPTS)
                    if attempt < _MAX_ATTEMPTS:
                        time.sleep(_RETRY_DELAY_SECONDS)
                    continue
                logger.error("Groq failed (%s): %s", resp.status_code, resp.text[:300])
                raise LLMProviderError(f"Groq rejected the request ({resp.status_code}).")
            except requests.RequestException as exc:
                last_exc = exc
                logger.warning("Groq network error (attempt %s/%s): %s", attempt, _MAX_ATTEMPTS, exc)
                if attempt < _MAX_ATTEMPTS:
                    time.sleep(_RETRY_DELAY_SECONDS)

        raise LLMProviderError("Groq is temporarily unavailable.") from last_exc

    def invoke_text(self, prompt: str) -> str:
        return self.invoke_messages([HumanMessage(content=prompt)])


class GeminiProvider:
    name = "gemini"

    def __init__(self, model: str | None = None):
        self._model = model or settings.GEMINI_MODEL

    def _client(self):
        if not settings.GEMINI_API_KEY:
            raise LLMProviderError("GEMINI_API_KEY is not configured.")
        return genai.Client(api_key=settings.GEMINI_API_KEY)

    def invoke_messages(self, messages: list) -> str:
        client = self._client()
        system_parts, contents = [], []
        for m in messages:
            if isinstance(m, SystemMessage):
                system_parts.append(m.content)
            elif isinstance(m, HumanMessage):
                contents.append(types.Content(role="user", parts=[types.Part(text=m.content)]))
            elif isinstance(m, AIMessage):
                contents.append(types.Content(role="model", parts=[types.Part(text=m.content)]))

        config = types.GenerateContentConfig(system_instruction="\n\n".join(system_parts) if system_parts else None)

        last_exc = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = client.models.generate_content(model=self._model, contents=contents, config=config)
                return self._extract_text(response)
            except genai_errors.ServerError as exc:
                last_exc = exc
                logger.warning("Gemini overloaded (attempt %s/%s)", attempt, _MAX_ATTEMPTS)
                if attempt < _MAX_ATTEMPTS:
                    time.sleep(_RETRY_DELAY_SECONDS)
            except genai_errors.ClientError as exc:
                logger.exception("Gemini client error")
                raise LLMProviderError("Gemini rejected the request. Check GEMINI_MODEL/GEMINI_API_KEY.") from exc
            except Exception as exc:
                logger.exception("Gemini call failed")
                raise LLMProviderError("Gemini is temporarily unavailable.") from exc

        raise LLMProviderError("Gemini is experiencing high demand.") from last_exc

    @staticmethod
    def _extract_text(response) -> str:
        text = getattr(response, "text", None)
        if text:
            return text
        try:
            return "".join(p.text for p in response.candidates[0].content.parts if getattr(p, "text", None))
        except Exception:
            return ""

    def invoke_text(self, prompt: str) -> str:
        return self.invoke_messages([HumanMessage(content=prompt)])


_PROVIDER_CLASSES = {"groq": GroqProvider, "gemini": GeminiProvider}


class FallbackLLM:
    """Tries each configured provider in order; falls through automatically on failure."""

    def __init__(self, provider_names: list[str], summary_model: bool = False):
        self._providers = []
        for name in provider_names:
            cls = _PROVIDER_CLASSES.get(name)
            if not cls:
                continue
            if name == "groq":
                model = settings.GROQ_SUMMARY_MODEL if summary_model else settings.GROQ_MODEL
            else:
                model = settings.GEMINI_SUMMARY_MODEL if summary_model else settings.GEMINI_MODEL
            self._providers.append(cls(model=model))

        if not self._providers:
            raise LLMProviderError("No LLM provider is configured. Check LLM_PROVIDERS in .env.")

    def invoke_messages(self, messages: list) -> str:
        last_exc = None
        for provider in self._providers:
            try:
                return provider.invoke_messages(messages)
            except LLMProviderError as exc:
                logger.warning("Provider '%s' failed, trying next: %s", provider.name, exc.message)
                last_exc = exc
        raise last_exc or LLMProviderError("All LLM providers failed.")

    def invoke_text(self, prompt: str) -> str:
        return self.invoke_messages([HumanMessage(content=prompt)])


def get_llm_provider(use_summary_model: bool = False):
    """Factory used by chat_service.py and memory_service.py."""
    return FallbackLLM(settings.LLM_PROVIDERS, summary_model=use_summary_model)