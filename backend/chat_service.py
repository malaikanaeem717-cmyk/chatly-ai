"""
Chat Service
============
Understand intent -> (maybe) retrieve+rerank document context -> build the
right prompt -> call the LLM -> save -> return. Document context only gets
injected when a chunk clears RELEVANCE_THRESHOLD — below that, the model
just answers from general knowledge, and is explicitly told never to
refuse or say "not found in document".

Separately, whenever the conversation HAS a document at all (even if no
specific chunk matched this particular message), the model is told the
document's filename exists — otherwise a generic message like "read this
file, I'll ask questions later" has no matching chunks, no context gets
injected, and the model wrongly guesses the file was never attached.
"""
from langchain_core.messages import HumanMessage, SystemMessage

from backend.config import settings
from backend.logging_config import logger
from backend import database as db
from backend.query_understanding import classify_intent
from backend.memory_service import MemoryService
from backend.embeddings import embed_query
from backend.retrieval import hybrid_retrieve, rerank, build_citations
from backend.llm_provider import get_llm_provider
from backend.image_service import ImageGenerationService
from backend.exceptions import ChatlyError

SYSTEM_PROMPT = (
    "You are Chatly AI, a helpful, knowledgeable assistant. Answer the user's question "
    "naturally and completely, the way a great ChatGPT-style assistant would. When relevant "
    "document context is provided below a question, use it as your primary source and explain "
    "it in your own words rather than copy-pasting. If the document only partially covers the "
    "topic, blend it with your own general knowledge to give a complete answer. If no document "
    "context is provided, simply answer from your general knowledge — never refuse or say "
    "information is 'missing from the document'. If the user has uploaded document(s) but this "
    "particular message doesn't need them (e.g. a greeting, or 'let's discuss this file'), "
    "acknowledge the document is available and ready rather than claiming it wasn't attached — "
    "you are always told below when document(s) exist in this conversation. You also have a "
    "real, working image generation feature built into this app — if the user asks whether you "
    "can generate/create images, say yes, and tell them they can either describe the image "
    "right in the chat box (it's auto-detected) or tap the '+' button and choose 'Create an "
    "image'. Never claim you can't generate images in this app. Give real, useful, complete "
    "answers every time."
)


class ChatService:
    def __init__(self):
        self.memory = MemoryService()
        self.llm = get_llm_provider()
        self.image_service = ImageGenerationService()

    def handle_message(self, user_id: str, conversation_id: str | None, text: str) -> dict:
        default_title = text[:40] + ("..." if len(text) > 40 else "")
        conversation = db.get_or_create_conversation(user_id, conversation_id, default_title)
        conv_id = conversation["id"]

        history_context = self.memory.get_context_messages(conv_id)
        intent = classify_intent(text, has_history=bool(history_context))

        db.add_message(conv_id, "user", text, message_type="text")

        # Auto-detect "make me an image of ..." style messages typed straight into
        # the normal chat box — the user shouldn't have to tap the image icon first.
        if intent["is_image_request"]:
            return self._handle_image_intent(conv_id, text)

        available_chunks = db.list_chunks(conv_id)
        used_context, citations, doc_names = "", [], []
        if available_chunks:
            doc_names = sorted({c["filename"] for c in available_chunks if c.get("filename")})
            used_context, citations = self._retrieve_context(text, available_chunks)

        prompt = self._build_prompt(text, used_context, doc_names)
        messages = [SystemMessage(content=SYSTEM_PROMPT), *history_context, HumanMessage(content=prompt)]
        reply = self.llm.invoke_messages(messages)

        db.add_message(conv_id, "assistant", reply, message_type="text", sources=citations)

        return {"conversation_id": conv_id, "reply": reply, "sources": citations, "intent": intent["intent"]}

    def _handle_image_intent(self, conv_id: str, text: str) -> dict:
        """
        Called when the user's plain chat message reads like an image request
        (e.g. "make an image of a sunset"). Generates the image right away and
        returns it in the normal chat response shape, so the frontend can
        render an image card without the user ever touching the '+' menu.

        IMPORTANT: `image` / `provider` must live inside `extra` — ChatResponse
        (models.py) only has an `extra: dict` field, no top-level `image` /
        `provider` fields, so anything placed outside `extra` gets silently
        stripped by FastAPI's response_model and never reaches the frontend.
        """
        try:
            result = self.image_service.generate(text, style="realistic", width=1024, height=1024)
            db.add_message(
                conv_id, "assistant", text, message_type="image",
                extra={"image": result["image"], "provider": result["provider"]},
            )
            return {
                "conversation_id": conv_id,
                "reply": text,
                "sources": [],
                "intent": "image_generation",
                "message_type": "image",
                "extra": {"image": result["image"], "provider": result["provider"]},
            }
        except ChatlyError as exc:
            logger.warning("Inline image generation failed: %s", exc.message)
            reply = f"⚠️ {exc.message}"
            db.add_message(conv_id, "assistant", reply, message_type="text")
            return {"conversation_id": conv_id, "reply": reply, "sources": [], "intent": "image_generation"}

    def _retrieve_context(self, query: str, chunks: list[dict]):
        try:
            query_embedding = embed_query(query)
            candidates = hybrid_retrieve(query, query_embedding, chunks)
            top = rerank(query, candidates)

            relevant = [c for c in top if c.get("rerank_score", c["score"]) >= settings.RELEVANCE_THRESHOLD]
            if not relevant:
                return "", []

            context_text = "\n\n---\n\n".join(
                f"[Source: {c['filename']}, section {c['chunk_index'] + 1}]\n{c['content']}" for c in relevant
            )
            return context_text, build_citations(relevant)
        except Exception:
            logger.exception("Retrieval pipeline failed — continuing without document context.")
            return "", []

    def _build_prompt(self, question: str, context: str, doc_names: list[str] | None = None) -> str:
        if context:
            return (
                "Relevant context retrieved from the user's uploaded document(s) (use as a primary "
                "source where it helps, blend with your own knowledge where it's only partial, and "
                f"ignore anything below that isn't relevant to the question):\n\n{context}\n\n"
                f"User's question: {question}"
            )
        if doc_names:
            names = ", ".join(doc_names)
            return (
                f"(Note: this conversation has {len(doc_names)} uploaded document(s) available: {names}. "
                "Nothing in them specifically matched this message, so just respond naturally — if "
                "relevant, acknowledge the document is there and ready; never claim it wasn't attached.)\n\n"
                f"User's message: {question}"
            )
        return question