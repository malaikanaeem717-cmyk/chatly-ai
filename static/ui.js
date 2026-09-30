// DOM rendering helpers. Nothing here calls the API — it only builds/updates elements.
const messagesEl = document.getElementById("messages");
const emptyStateEl = document.getElementById("emptyState");

export function hideEmptyState() {
  emptyStateEl.style.display = "none";
}

export function showEmptyState(text) {
  emptyStateEl.innerHTML = text
    ? escapeHtml(text)
    : `<div class="greeting-title">${escapeHtml(getGreeting())}</div>
       <div class="greeting-sub">Start a new chat, upload a document, or generate an image</div>`;
  emptyStateEl.style.display = "block";
  messagesEl.appendChild(emptyStateEl);
}

function getGreeting() {
  const hour = new Date().getHours();
  const period = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : hour < 21 ? "Good evening" : "Good night";
  const email = localStorage.getItem("chatly_email") || "";
  const local = email.split("@")[0] || "";
  const name = local.replace(/[0-9]+/g, "").replace(/[._-]+/g, " ").trim();
  const displayName = name ? name.replace(/\b\w/g, (c) => c.toUpperCase()) : "";
  return displayName ? `${period}, ${displayName} \uD83D\uDC4B` : `${period} \uD83D\uDC4B`;
}

export function clearMessages() {
  messagesEl.innerHTML = "";
}

export function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function safeMarkdown(text) {
  try {
    return typeof marked !== "undefined" ? marked.parse(text) : escapeHtml(text);
  } catch {
    return escapeHtml(text);
  }
}

function timeAgo(dateString) {
  if (!dateString) return "";
  const diffMs = Date.now() - new Date(dateString).getTime();
  const sec = Math.floor(diffMs / 1000);
  if (sec < 60) return "just now";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} minute${min !== 1 ? "s" : ""} ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} hour${hr !== 1 ? "s" : ""} ago`;
  const day = Math.floor(hr / 24);
  return `${day} day${day !== 1 ? "s" : ""} ago`;
}

/**
 * Renders one message bubble with a ChatGPT-style action row underneath:
 * relative timestamp, then icon buttons. Which icons appear depends on
 * role: user messages get regenerate + edit + copy; assistant messages
 * get regenerate + copy (editing an AI reply doesn't make sense).
 *
 * onRegenerate/onEdit are optional callbacks — pass them only when the
 * caller actually supports that action for this message.
 */
export function renderTextMessage(role, content, sources, onEdit, onRegenerate, createdAt) {
  const wrap = document.createElement("div");
  wrap.className = "msg-wrap " + (role === "user" ? "user" : "bot");
  wrap.dataset.createdAt = createdAt || new Date().toISOString();

  const div = document.createElement("div");
  div.className = "msg " + (role === "user" ? "user" : "bot");
  if (role === "user") {
    div.textContent = content;
  } else {
    div.innerHTML = safeMarkdown(content || "");
    if (sources && sources.length) {
      const row = document.createElement("div");
      row.className = "sources-row";
      row.innerHTML = sources
        .map((s) => `<span class="source-chip"><b>${escapeHtml(s.document)}</b> \u00b7 \u00a71 ${s.section}</span>`)
        .join("");
      div.appendChild(row);
    }
  }
  wrap.appendChild(div);

  const actions = document.createElement("div");
  actions.className = "msg-actions";

  const timeEl = document.createElement("span");
  timeEl.className = "msg-time";
  timeEl.textContent = timeAgo(wrap.dataset.createdAt);
  actions.appendChild(timeEl);

  if (onRegenerate) {
    const regenBtn = document.createElement("button");
    regenBtn.className = "msg-action-btn";
    regenBtn.title = "Regenerate";
    regenBtn.innerHTML = "\u21bb";
    regenBtn.addEventListener("click", () => onRegenerate(regenBtn));
    actions.appendChild(regenBtn);
  }

  if (role === "user" && onEdit) {
    const editBtn = document.createElement("button");
    editBtn.className = "msg-action-btn";
    editBtn.title = "Edit";
    editBtn.innerHTML = "\u270f\ufe0f";
    editBtn.addEventListener("click", () => onEdit(content));
    actions.appendChild(editBtn);
  }

  const copyBtn = document.createElement("button");
  copyBtn.className = "msg-action-btn";
  copyBtn.title = "Copy";
  copyBtn.innerHTML = "\ud83d\udccb";
  copyBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(content || "");
      copyBtn.innerHTML = "\u2705";
      setTimeout(() => (copyBtn.innerHTML = "\ud83d\udccb"), 1200);
    } catch {
      /* clipboard blocked (e.g. non-HTTPS) — silently ignore */
    }
  });
  actions.appendChild(copyBtn);
  wrap.appendChild(actions);

  messagesEl.appendChild(wrap);
  scrollToBottom();
  return wrap;
}

export function showTyping() {
  const div = document.createElement("div");
  div.className = "typing";
  div.id = "typingIndicator";
  div.innerHTML = "<span></span><span></span><span></span>";
  messagesEl.appendChild(div);
  scrollToBottom();
}

export function hideTyping() {
  document.getElementById("typingIndicator")?.remove();
}

// ---- file (document upload) card ----
export function renderFileCard(id, filename, chunkCount, processing, errorMsg) {
  const div = document.createElement("div");
  div.className = "msg file-card";
  div.id = id;
  div.innerHTML = fileCardHTML(filename, chunkCount, processing, errorMsg);
  messagesEl.appendChild(div);
  scrollToBottom();
  return div;
}

export function updateFileCard(id, filename, chunkCount, processing, errorMsg) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = fileCardHTML(filename, chunkCount, processing, errorMsg);
}

function fileCardHTML(filename, chunkCount, processing, errorMsg) {
  if (processing) {
    return `<div class="file-card-inner"><div class="file-icon">\uD83D\uDCC4</div>
      <div class="file-info"><div class="file-name">${escapeHtml(filename)}</div>
      <div class="file-status">Reading document...</div></div>
      <div class="file-spinner"></div></div>`;
  }
  if (errorMsg) {
    return `<div class="file-card-inner error"><div class="file-icon">\u26A0\uFE0F</div>
      <div class="file-info"><div class="file-name">${escapeHtml(filename)}</div>
      <div class="file-status">${escapeHtml(errorMsg)}</div></div></div>`;
  }
  return `<div class="file-card-inner"><div class="file-icon">\uD83D\uDCC4</div>
    <div class="file-info"><div class="file-name">${escapeHtml(filename)}</div>
    <div class="file-status">\u2705 ${chunkCount} sections indexed</div></div></div>`;
}

// ---- image generation card ----
const _imageLoadingIntervals = {};
// ---- image generation card ----
const _imageLoadingTimers = {}; // { [id]: { percentInterval } }

export function renderImageLoadingCard(id) {
  const div = document.createElement("div");
  div.id = id;
  div.className = "image-generating";

  const rows = 8, cols = 14;
  let dotsHTML = "";
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const delay = (r + c) * 0.06;
      dotsHTML += `<span class="ig-dot" style="animation-delay:${delay}s"></span>`;
    }
  }

  div.innerHTML = `
    <div class="ig-title">Creating image</div>
    <div class="ig-dotgrid">${dotsHTML}</div>
    <div class="ig-percent">0%</div>`;
  messagesEl.appendChild(div);
  scrollToBottom();

  // Simulated progress — climbs quickly at first, then slows and caps at 90%
  // until the real image actually arrives (we have no true progress signal
  // from the provider, so this just gives the same reassuring motion ChatGPT's
  // UI has rather than a static spinner).
  let percent = 0;
  const percentEl = div.querySelector(".ig-percent");
  const percentInterval = setInterval(() => {
    if (percent >= 90) return;
    percent += percent < 40 ? 7 : percent < 70 ? 4 : 1;
    percent = Math.min(percent, 90);
    if (percentEl) percentEl.textContent = percent + "%";
  }, 350);

  _imageLoadingTimers[id] = { percentInterval };
}

function _clearImageLoadingTimer(id) {
  const timer = _imageLoadingTimers[id];
  if (timer) {
    clearInterval(timer.percentInterval);
    delete _imageLoadingTimers[id];
  }
}

export function renderImageMessage(imageData, prompt, provider) {
  const id = "imgcard-" + Date.now() + Math.random().toString(36).slice(2);
  renderImageLoadingCard(id);
  updateImageCardDone(id, imageData, prompt, provider);
}

export function updateImageCardDone(id, imageData, prompt, provider) {
  _clearImageLoadingTimer(id);
  const el = document.getElementById(id);
  if (!el) return;

  el.className = "";
  el.style.cssText = "background:none; border:none; padding:0; margin:8px 0; box-shadow:none; max-width:min(420px, 90%);";
  el.innerHTML = `
    <div style="position:relative; display:inline-block; max-width:100%;">
      <img src="${imageData}" alt="${escapeHtml(prompt)}" style="display:block; width:100%; height:auto; border-radius:12px; cursor:zoom-in;">
      <div class="image-download-corner" style="position:absolute; bottom:10px; right:10px; display:flex; align-items:center; gap:6px;">
        <span class="image-download-label" style="opacity:0; transition:opacity .2s ease; background:rgba(0,0,0,0.75); color:#fff; font-size:12px; padding:4px 8px; border-radius:6px; white-space:nowrap;">Download</span>
        <button class="image-download-icon-btn" title="Download" style="width:34px; height:34px; border-radius:50%; border:none; background:rgba(0,0,0,0.6); color:#fff; font-size:15px; cursor:pointer; display:flex; align-items:center; justify-content:center;">\u2b07\ufe0f</button>
      </div>
    </div>`;

  el.querySelector("img").addEventListener("click", () => openLightbox(imageData));

  const iconBtn = el.querySelector(".image-download-icon-btn");
  const label = el.querySelector(".image-download-label");
  iconBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    label.style.opacity = "1";
    const a = document.createElement("a");
    a.href = imageData;
    a.download = "chatly-image.jpg";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => { label.style.opacity = "0"; }, 1500);
  });

  scrollToBottom();
}

export function updateImageCardError(id, errorMsg) {
  _clearImageLoadingTimer(id);
  const el = document.getElementById(id);
  if (!el) return;
  el.className = "msg image-card error";
  el.textContent = `\u26A0\uFE0F ${errorMsg}`;
}
// ---- lightbox: click any generated image to view it enlarged ----
function ensureLightbox() {
  let lb = document.getElementById("lightbox");
  if (!lb) {
    lb = document.createElement("div");
    lb.id = "lightbox";
    lb.innerHTML = `<button class="lightbox-close">\u2715</button><img>`;
    document.body.appendChild(lb);
    lb.addEventListener("click", (e) => {
      if (e.target === lb || e.target.classList.contains("lightbox-close")) closeLightbox();
    });
  }
  return lb;
}
function openLightbox(imageData) {
  const lb = ensureLightbox();
  lb.querySelector("img").src = imageData;
  lb.classList.add("show");
}
function closeLightbox() {
  document.getElementById("lightbox")?.classList.remove("show");
}

// ---- sidebar: conversation list ----
export function renderConversationList(container, conversations, activeId, onOpen, onRename, onShare, onDelete) {
  container.innerHTML = "";
  if (!conversations.length) {
    const empty = document.createElement("div");
    empty.className = "doc-empty";
    empty.textContent = "No conversations yet.";
    container.appendChild(empty);
    return;
  }
  conversations.forEach((c) => {
    const div = document.createElement("div");
    div.className = "chat-item" + (c.id === activeId ? " active" : "");
    div.innerHTML = `
      <span class="chat-item-title">${escapeHtml(c.title)}</span>
      <button class="kebab-btn" title="More">\u22ee</button>
      <div class="chat-menu">
        <div class="chat-menu-item" data-action="rename">\u270f\ufe0f Rename</div>
        <div class="chat-menu-item" data-action="share">\ud83d\udd17 Share</div>
        <div class="chat-menu-item danger" data-action="delete">\ud83d\uddd1\ufe0f Delete</div>
      </div>`;

    div.querySelector(".chat-item-title").addEventListener("click", () => onOpen(c.id, c.title));

    const kebabBtn = div.querySelector(".kebab-btn");
    const menu = div.querySelector(".chat-menu");
    kebabBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      document.querySelectorAll(".chat-menu.show").forEach((m) => { if (m !== menu) m.classList.remove("show"); });
      menu.classList.toggle("show");
    });
    menu.querySelector('[data-action="rename"]').addEventListener("click", (e) => {
      e.stopPropagation();
      menu.classList.remove("show");
      onRename(c.id, c.title);
    });
    menu.querySelector('[data-action="share"]').addEventListener("click", (e) => {
      e.stopPropagation();
      menu.classList.remove("show");
      onShare(c.id);
    });
    menu.querySelector('[data-action="delete"]').addEventListener("click", (e) => {
      e.stopPropagation();
      menu.classList.remove("show");
      onDelete(c.id);
    });

    container.appendChild(div);
  });
}

// ---- sidebar: document list ----
export function renderDocumentList(container, documents, onDelete) {
  container.innerHTML = "";
  if (!documents.length) {
    const empty = document.createElement("div");
    empty.className = "doc-empty";
    empty.textContent = "No documents uploaded in this chat yet.";
    container.appendChild(empty);
    return;
  }
  documents.forEach((d) => {
    const div = document.createElement("div");
    div.className = "doc-item";
    const statusText = d.status === "ready" ? `${d.chunk_count} sections` : d.status === "failed" ? (d.error || "Failed") : "Processing...";
    div.innerHTML = `
      <div class="doc-row">
        <span class="doc-name">${escapeHtml(d.filename)}</span>
        <span class="del-btn">\u2715</span>
      </div>
      <span class="doc-status ${d.status}">${escapeHtml(statusText)}</span>`;
    div.querySelector(".del-btn").addEventListener("click", () => onDelete(d.id));
    container.appendChild(div);
  });
}

export function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}