"""Conversation memory — recent turns verbatim, older turns rolled into a summary."""
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from backend.config import settings
from backend.logging_config import logger
from backend import database as db
from backend.llm_provider import get_llm_provider


class MemoryService:
    def get_context_messages(self, conversation_id: str) -> list:
        all_messages = db.list_messages(conversation_id)
        text_messages = [m for m in all_messages if m["message_type"] in ("text", "image")]

        if len(text_messages) > settings.MEMORY_SUMMARY_TRIGGER:
            self._maybe_refresh_summary(conversation_id, text_messages)

        conv = db.get_conversation(conversation_id)
        recent = text_messages[-settings.MEMORY_RECENT_TURNS:]

        context = []
        if conv and conv.get("summary"):
            context.append(SystemMessage(content=f"Summary of earlier conversation (background context only):\n{conv['summary']}"))
        for m in recent:
            context.append(HumanMessage(content=m["content"]) if m["role"] == "user" else AIMessage(content=m["content"]))
        return context

    def _maybe_refresh_summary(self, conversation_id: str, text_messages: list):
        to_summarize = text_messages[: -settings.MEMORY_RECENT_TURNS]
        if not to_summarize:
            return
        transcript = "\n".join(f"{m['role']}: {m['content']}" for m in to_summarize)
        prompt = (
            "Summarize the following conversation history in a few concise sentences, "
            "keeping any facts, names, decisions, or preferences that might matter for "
            "answering future questions:\n\n" + transcript
        )
        try:
            summary = get_llm_provider(use_summary_model=True).invoke_text(prompt)
            db.update_conversation_summary(conversation_id, summary)
        except Exception:
            logger.warning("Conversation summarization failed — continuing without an updated summary.")