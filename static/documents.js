import { api } from "./api.js";
import { state } from "./state.js";
import * as ui from "./ui.js";

const fileInput = document.getElementById("fileInput");
const attachmentBar = document.getElementById("attachmentBar");

function escapeHtmlLocal(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function renderChip() {
  if (!state.pendingFile) {
    attachmentBar.innerHTML = "";
    attachmentBar.classList.remove("show");
    return;
  }
  attachmentBar.classList.add("show");
  attachmentBar.innerHTML = `
    <div class="attachment-chip">
      <span>\uD83D\uDCC4 ${escapeHtmlLocal(state.pendingFile.name)}</span>
      <span class="remove" id="removeAttachment">\u2715</span>
    </div>`;
  document.getElementById("removeAttachment").addEventListener("click", () => {
    state.pendingFile = null;
    fileInput.value = "";
    renderChip();
  });
}

/**
 * Just remembers the picked file and shows a small chip above the input —
 * it does NOT upload immediately. The actual upload happens in
 * uploadPendingFile(), called right when the user hits Send, so the file
 * and whatever prompt they typed travel together as one action (matches
 * how ChatGPT attaches a file to the composer before sending).
 */
export function initDocumentUpload() {
  fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];
    if (!file) return;
    state.pendingFile = file;
    renderChip();
  });
}

export function hasPendingFile() {
  return !!state.pendingFile;
}

export async function uploadPendingFile() {
  const file = state.pendingFile;
  if (!file) return null;

  state.pendingFile = null;
  fileInput.value = "";
  renderChip();

  const cardId = "filecard-temp-" + Date.now();
  ui.hideEmptyState();
  ui.renderFileCard(cardId, file.name, null, true);

  try {
    const result = await api.uploadDocument(state.currentConversationId, file);
    if (!result) return null; // logged out mid-request

    if (!state.currentConversationId) {
      state.currentConversationId = result.conversation_id;
    }
    if (result.success) {
      ui.updateFileCard(cardId, result.filename, result.chunk_count, false, null);
    } else {
      ui.updateFileCard(cardId, result.filename, null, false, result.error);
    }
    return result;
  } catch (err) {
    ui.updateFileCard(cardId, file.name, null, false, "Upload failed. Please check the server.");
    return null;
  }
}
/**
 * Listens for paste anywhere on the page (Ctrl+V / right-click paste) and
 * intercepts it if the clipboard holds a file — an image (e.g. a screenshot)
 * or an actual file (e.g. a PDF copied from File Explorer). Plain text
 * paste is left alone so it goes into the input box normally.
 */
export function initPasteUpload() {
  document.addEventListener("paste", (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of items) {
      if (item.kind === "file") {
        const file = item.getAsFile();
        if (file) {
          e.preventDefault();
          state.pendingFile = file;
          renderChip();
        }
        return;
      }
    }
  });
}