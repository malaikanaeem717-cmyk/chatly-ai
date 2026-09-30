// API client — every backend call goes through here. On a 401, it tries a
// silent token refresh first (see auth.js) and retries the request once
// before giving up and logging out — this is what stops people getting
// logged out just because some time passed.
import { authHeader, refreshAccessToken, logout } from "./auth.js";

async function request(path, options = {}) {
  const headers = { ...authHeader(), ...(options.headers || {}) };
  let res = await fetch(path, { ...options, headers });

  if (res.status === 401) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      const retryHeaders = { ...authHeader(), ...(options.headers || {}) };
      res = await fetch(path, { ...options, headers: retryHeaders });
    }
    if (res.status === 401) {
      logout();
      return null;
    }
  }

  return res.json();
}

export const api = {
  sendChatMessage(message, conversationId) {
    return request("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, conversation_id: conversationId }),
    });
  },

  listConversations() {
    return request("/api/chat/conversations");
  },

  getMessages(conversationId) {
    return request(`/api/chat/conversations/${conversationId}/messages`);
  },

  deleteConversation(conversationId) {
    return request(`/api/chat/conversations/${conversationId}`, { method: "DELETE" });
  },

  renameConversation(conversationId, title) {
    return request(`/api/chat/conversations/${conversationId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
  },

  uploadDocument(conversationId, file) {
    const formData = new FormData();
    formData.append("file", file);
    const params = conversationId ? `?conversation_id=${conversationId}` : "";
    return request(`/api/documents/upload${params}`, { method: "POST", body: formData });
  },

  listDocuments(conversationId) {
    return request(`/api/documents/${conversationId}`);
  },

  deleteDocument(documentId) {
    return request(`/api/documents/${documentId}`, { method: "DELETE" });
  },

  generateImage(prompt, style, conversationId) {
    return request("/api/images/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, style, conversation_id: conversationId }),
    });
  },
};