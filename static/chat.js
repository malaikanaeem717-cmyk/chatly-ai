import { api } from "./api.js";
import { state } from "./state.js";
import * as ui from "./ui.js";
import * as documents from "./documents.js";

const chatTitleEl = document.getElementById("chatTitle");
const chatListEl = document.getElementById("chatList");
const inputEl = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");

export async function refreshConversationList() {
  const conversations = (await api.listConversations()) || [];
  ui.renderConversationList(
    chatListEl, conversations, state.currentConversationId,
    openConversation, renameConversationPrompt, shareConversation, deleteConversation
  );
}

export async function openConversation(id, title) {
  state.currentConversationId = id;
  chatTitleEl.textContent = title;
  ui.clearMessages();

  const messages = (await api.getMessages(id)) || [];
  if (!messages.length) {
    ui.showEmptyState();
  } else {
    let lastUserText = "";
    messages.forEach((m) => {
      if (m.message_type === "image" && m.extra?.image) {
        const cardId = "imgcard-" + m.id;
        ui.renderImageLoadingCard(cardId);
        ui.updateImageCardDone(cardId, m.extra.image, m.content, m.extra.provider || "");
      } else if (m.message_type === "file_notice") {
        const meta = safeJson(m.content);
        ui.renderFileCard("filecard-" + m.id, meta.filename, meta.chunk_count, false);
      } else if (m.role === "user") {
        lastUserText = m.content;
        ui.renderTextMessage("user", m.content, null, editUserMessage, () => regenerateFrom(m.content), m.created_at);
      } else {
        ui.renderTextMessage("assistant", m.content, m.sources, null, () => regenerateFrom(lastUserText), m.created_at);
      }
    });
  }

  await refreshConversationList();
  window.dispatchEvent(new CustomEvent("conversation-opened", { detail: { id } }));
}

export function startNewChatView() {
  state.currentConversationId = null;
  chatTitleEl.textContent = "New Chat";
  ui.clearMessages();
  ui.showEmptyState();
  refreshConversationList();
  window.dispatchEvent(new CustomEvent("conversation-opened", { detail: { id: null } }));
}

async function deleteConversation(id) {
  await api.deleteConversation(id);
  if (id === state.currentConversationId) startNewChatView();
  refreshConversationList();
}

async function renameConversationPrompt(id, currentTitle) {
  const newTitle = window.prompt("Rename chat:", currentTitle);
  if (!newTitle || !newTitle.trim() || newTitle.trim() === currentTitle) return;
  const result = await api.renameConversation(id, newTitle.trim());
  if (result) {
    if (id === state.currentConversationId) chatTitleEl.textContent = newTitle.trim();
    refreshConversationList();
  }
}

function shareConversation(id) {
  const url = `${window.location.origin}/?c=${id}`;
  const done = () => alert("Link copied! Whoever opens it needs to be logged into this same account to view it.");
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(url).then(done).catch(() => window.prompt("Copy this link:", url));
  } else {
    window.prompt("Copy this link:", url);
  }
}

export async function sendTextMessage() {
  const text = inputEl.value.trim();
  if (!text && !documents.hasPendingFile()) return;
  inputEl.value = "";
  await sendMessageText(text);
}

/**
 * Sends `text` as a fresh user turn (uploading any attached file first so
 * they travel together) and renders the reply. Also used by the
 * "regenerate" icon — regenerate asks the same question again and adds
 * the new answer below; it doesn't delete/overwrite the original turn,
 * since the backend doesn't support editing history in place.
 */
async function sendMessageText(text) {
  ui.hideEmptyState();
  sendBtn.disabled = true;

  if (documents.hasPendingFile()) {
    await documents.uploadPendingFile();
  }

  if (!text) {
    sendBtn.disabled = false;
    refreshConversationList();
    return;
  }

  const nowIso = new Date().toISOString();
  ui.renderTextMessage("user", text, null, editUserMessage, () => regenerateFrom(text), nowIso);
  ui.showTyping();

  try {
    const result = await api.sendChatMessage(text, state.currentConversationId);
    ui.hideTyping();
    if (!result) return; // logged out mid-request

    if (!state.currentConversationId) {
      state.currentConversationId = result.conversation_id;
      chatTitleEl.textContent = text.length > 30 ? text.slice(0, 30) + "..." : text;
    }
    if (result.message_type === "image" && result.extra?.image) {
      ui.renderImageMessage(result.extra.image, result.reply || text, result.extra.provider || "");
    } else {
      ui.renderTextMessage("assistant", result.reply, result.sources, null, () => regenerateFrom(text), new Date().toISOString());
    }
    refreshConversationList();
  } catch (err) {
    ui.hideTyping();
    ui.renderTextMessage("assistant", "\u26A0\uFE0F Could not reach the server. Please try again.");
  }

  sendBtn.disabled = false;
  inputEl.focus();
}

async function regenerateFrom(text) {
  if (!text) return;
  await sendMessageText(text);
}

export function editUserMessage(text) {
  inputEl.value = text;
  inputEl.focus();
  inputEl.setSelectionRange(text.length, text.length);
}

function safeJson(str) {
  try {
    return JSON.parse(str);
  } catch {
    return {};
  }
}