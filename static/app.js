import { requireLogin, getEmail, logout } from "./auth.js";
import { state } from "./state.js";
import * as chat from "./chat.js";
import * as documents from "./documents.js";
import * as images from "./images.js";
import * as ui from "./ui.js";
import { initImageEditor } from "./image_editor.js";

requireLogin(); // redirects to /login if no token — everything below assumes we're authenticated

const inputEl = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");
const newChatBtn = document.getElementById("newChatBtn");
const menuBtn = document.getElementById("menuBtn");
const closeSidebarBtn = document.getElementById("closeSidebarBtn");
const sidebarEl = document.getElementById("sidebar");
const sidebarOverlay = document.getElementById("sidebarOverlay");
const userEmailEl = document.getElementById("userEmail");
const logoutBtn = document.getElementById("logoutBtn");
const fileInput = document.getElementById("fileInput");

const plusBtn = document.getElementById("plusBtn");
const plusMenu = document.getElementById("plusMenu");
const menuUpload = document.getElementById("menuUpload");
const menuImage = document.getElementById("menuImage");

userEmailEl.textContent = getEmail() || "";
logoutBtn.addEventListener("click", logout);

// ---- Splash screen bubbles ----
function buildBubbles() {
  const field = document.getElementById("bubbleField");
  const count = window.innerWidth < 600 ? 14 : 22;
  for (let i = 0; i < count; i++) {
    const b = document.createElement("div");
    b.className = "bubble";
    const size = 14 + Math.random() * 46;
    b.style.width = size + "px";
    b.style.height = size + "px";
    b.style.left = Math.random() * 100 + "%";
    b.style.setProperty("--drift", (Math.random() * 60 - 30) + "px");
    b.style.animationDuration = 5 + Math.random() * 5 + "s";
    b.style.animationDelay = Math.random() * 4 + "s";
    field.appendChild(b);
  }
}
buildBubbles();
window.addEventListener("load", () => {
  setTimeout(() => {
    const splash = document.getElementById("splash");
    const appEl = document.getElementById("app");
    splash.classList.add("leaving");
    appEl.classList.add("show"); // fade the main screen in as the logo shrinks away
    setTimeout(() => splash.classList.add("hide"), 500);
  }, 1600);
});

// ---- Mobile sidebar ----
function openSidebar() {
  sidebarEl.classList.add("open");
  sidebarOverlay.classList.add("show");
}
function closeSidebar() {
  sidebarEl.classList.remove("open");
  sidebarOverlay.classList.remove("show");
}
menuBtn.addEventListener("click", openSidebar);
closeSidebarBtn.addEventListener("click", closeSidebar);
sidebarOverlay.addEventListener("click", closeSidebar);

// ---- New chat / conversation switching ----
newChatBtn.addEventListener("click", () => {
  chat.startNewChatView();
  closeSidebar();
});

window.addEventListener("conversation-opened", () => {
  closeSidebar();
});

// ---- Unified "+" menu: upload a document OR create an image ----
function closePlusMenu() {
  plusMenu.classList.remove("show");
}
function togglePlusMenu() {
  plusMenu.classList.toggle("show");
}
plusBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  if (state.imageMode) {
    images.setImageMode(false);
    return;
  }
  togglePlusMenu();
});
document.addEventListener("click", (e) => {
  if (!plusMenu.contains(e.target) && e.target !== plusBtn) closePlusMenu();
  document.querySelectorAll(".chat-menu.show").forEach((m) => m.classList.remove("show"));
});
menuUpload.addEventListener("click", () => {
  closePlusMenu();
  fileInput.click();
});
menuImage.addEventListener("click", () => {
  closePlusMenu();
  images.setImageMode(!state.imageMode);
});

// ---- Send button routes to chat or image generation ----
async function handleSend() {
  const text = inputEl.value.trim();
  if (!text && !documents.hasPendingFile()) return;

  if (state.imageMode) {
    if (!text) return; // image generation always needs a prompt
    inputEl.value = "";
    await images.generateImage(text);
    inputEl.focus();
    return;
  }
  await chat.sendTextMessage();
}

sendBtn.addEventListener("click", handleSend);
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter") handleSend();
});

// ---- Wire up feature modules ----
documents.initDocumentUpload();
documents.initPasteUpload();
images.initImageMode();
initImageEditor((editedImageData) => {
  // The editor hands back a flattened image (base image + text layers).
  // It's added to the current chat view immediately. Note: this edited
  // version is a client-side composite only — it isn't re-uploaded to the
  // backend, so it won't reappear if you reopen this conversation later.
  ui.renderImageMessage(editedImageData, "Edited image", "text editor");
});

// ---- Boot ----
// A "Share" link looks like /?c=<conversationId> — open that chat directly
// if present (the person opening it must be logged into the same account;
// this is a personal quick-link, not public sharing of chat content).
const sharedChatId = new URLSearchParams(window.location.search).get("c");
if (sharedChatId) {
  chat.openConversation(sharedChatId, "Shared chat");
} else {
  chat.startNewChatView();
}