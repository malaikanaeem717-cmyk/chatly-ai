import { api } from "./api.js";
import { state } from "./state.js";
import * as ui from "./ui.js";

const imageStylesBar = document.getElementById("imageStylesBar");
const inputEl = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");
const chatTitleEl = document.getElementById("chatTitle");
const plusBtn = document.getElementById("plusBtn");

export function setImageMode(on) {
  state.imageMode = on;
  plusBtn.classList.toggle("active", on);
  imageStylesBar.classList.toggle("show", on);
  inputEl.placeholder = on ? "Describe the image you want to create..." : "Type a message...";
}

export function initImageMode() {
  imageStylesBar.addEventListener("click", (e) => {
    const chip = e.target.closest(".style-chip");
    if (!chip) return;
    document.querySelectorAll(".style-chip").forEach((c) => c.classList.remove("active"));
    chip.classList.add("active");
    state.imageStyle = chip.dataset.style;
  });
}

export async function generateImage(prompt) {
  ui.hideEmptyState();
  ui.renderTextMessage("user", prompt);

  const cardId = "imgcard-" + Date.now();
  ui.renderImageLoadingCard(cardId);
  sendBtn.disabled = true;

  try {
    const result = await api.generateImage(prompt, state.imageStyle, state.currentConversationId);
    if (!result) return; // logged out mid-request

    if (!state.currentConversationId && result.conversation_id) {
      state.currentConversationId = result.conversation_id;
      const title = "\uD83D\uDDBC\uFE0F " + (prompt.length > 26 ? prompt.slice(0, 26) + "..." : prompt);
      chatTitleEl.textContent = title;
    }

    if (result.success) {
      ui.updateImageCardDone(cardId, result.image, prompt, result.provider);
    } else {
      ui.updateImageCardError(cardId, result.error || "Image generation failed.");
    }
  } catch (err) {
    ui.updateImageCardError(cardId, "Could not reach the server. Please try again.");
  }

  sendBtn.disabled = false;
}
