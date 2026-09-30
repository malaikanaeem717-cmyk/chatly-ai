// Basic Canva-style text-on-image editor. Not a full design tool — it
// supports what was asked for: add text layers on top of a generated
// image, drag them into place, adjust font/size/color/bold, then save a
// new flattened image. Opened via the "open-image-editor" event (fired
// from ui.js when someone clicks "Edit Text" on an image card).
const overlay = document.getElementById("editorOverlay");
const canvas = document.getElementById("editorCanvas");
const ctx = canvas.getContext("2d");
const closeBtn = document.getElementById("editorCloseBtn");
const addTextBtn = document.getElementById("addTextBtn");
const deleteLayerBtn = document.getElementById("deleteLayerBtn");
const textInput = document.getElementById("layerTextInput");
const fontSelect = document.getElementById("layerFontSelect");
const sizeInput = document.getElementById("layerSizeInput");
const colorInput = document.getElementById("layerColorInput");
const boldInput = document.getElementById("layerBoldInput");
const layersListEl = document.getElementById("layersList");
const saveBtn = document.getElementById("saveEditBtn");

let baseImage = null;
let layers = []; // { id, text, font, size, color, bold, x, y }
let selectedId = null;
let dragging = false;
let dragOffset = { x: 0, y: 0 };
let onSaveCallback = null;

window.addEventListener("open-image-editor", (e) => {
  openEditor(e.detail.imageData, e.detail.prompt);
});

function openEditor(imageData) {
  layers = [];
  selectedId = null;
  const img = new Image();
  img.onload = () => {
    baseImage = img;
    const maxW = 760, maxH = 520;
    const scale = Math.min(1, maxW / img.width, maxH / img.height);
    canvas.width = img.width * scale;
    canvas.height = img.height * scale;
    render();
    overlay.classList.add("show");
  };
  img.src = imageData;
}

function closeEditor() {
  overlay.classList.remove("show");
}
closeBtn.addEventListener("click", closeEditor);
overlay.addEventListener("click", (e) => {
  if (e.target === overlay) closeEditor();
});

function fontString(layer) {
  return `${layer.bold ? "bold " : ""}${layer.size}px ${layer.font}`;
}

function render() {
  if (!baseImage) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(baseImage, 0, 0, canvas.width, canvas.height);

  layers.forEach((layer) => {
    ctx.font = fontString(layer);
    ctx.fillStyle = layer.color;
    ctx.textBaseline = "top";
    ctx.shadowColor = "rgba(0,0,0,0.5)";
    ctx.shadowBlur = 3;
    ctx.fillText(layer.text, layer.x, layer.y);
    ctx.shadowBlur = 0;

    if (layer.id === selectedId) {
      const metrics = ctx.measureText(layer.text);
      const w = metrics.width;
      const h = layer.size * 1.2;
      ctx.strokeStyle = "#7c6cf0";
      ctx.setLineDash([5, 4]);
      ctx.lineWidth = 1.5;
      ctx.strokeRect(layer.x - 4, layer.y - 4, w + 8, h + 8);
      ctx.setLineDash([]);
    }
  });

  renderLayersList();
}

function renderLayersList() {
  layersListEl.innerHTML = "";
  layers.forEach((layer) => {
    const item = document.createElement("div");
    item.className = "editor-layer-item" + (layer.id === selectedId ? " active" : "");
    item.textContent = layer.text || "(empty text)";
    item.addEventListener("click", () => selectLayer(layer.id));
    layersListEl.appendChild(item);
  });
}

function hitTest(px, py) {
  for (let i = layers.length - 1; i >= 0; i--) {
    const layer = layers[i];
    ctx.font = fontString(layer);
    const metrics = ctx.measureText(layer.text);
    const w = metrics.width;
    const h = layer.size * 1.2;
    if (px >= layer.x && px <= layer.x + w && py >= layer.y && py <= layer.y + h) {
      return layer;
    }
  }
  return null;
}

function selectLayer(id) {
  selectedId = id;
  const layer = layers.find((l) => l.id === id);
  if (layer) {
    textInput.value = layer.text;
    fontSelect.value = layer.font;
    sizeInput.value = layer.size;
    colorInput.value = layer.color;
    boldInput.checked = layer.bold;
  }
  render();
}

addTextBtn.addEventListener("click", () => {
  const id = "layer-" + Date.now();
  layers.push({
    id, text: "Your text here", font: fontSelect.value, size: Number(sizeInput.value),
    color: colorInput.value, bold: boldInput.checked,
    x: canvas.width / 2 - 60, y: canvas.height / 2 - 20,
  });
  selectLayer(id);
});

deleteLayerBtn.addEventListener("click", () => {
  if (!selectedId) return;
  layers = layers.filter((l) => l.id !== selectedId);
  selectedId = layers.length ? layers[layers.length - 1].id : null;
  render();
});

function updateSelectedLayer() {
  const layer = layers.find((l) => l.id === selectedId);
  if (!layer) return;
  layer.text = textInput.value;
  layer.font = fontSelect.value;
  layer.size = Number(sizeInput.value);
  layer.color = colorInput.value;
  layer.bold = boldInput.checked;
  render();
}
[textInput, fontSelect, sizeInput, colorInput, boldInput].forEach((el) => {
  el.addEventListener("input", updateSelectedLayer);
  el.addEventListener("change", updateSelectedLayer);
});

canvas.addEventListener("mousedown", (e) => {
  const rect = canvas.getBoundingClientRect();
  const px = e.clientX - rect.left, py = e.clientY - rect.top;
  const layer = hitTest(px, py);
  if (layer) {
    selectLayer(layer.id);
    dragging = true;
    dragOffset = { x: px - layer.x, y: py - layer.y };
  } else {
    selectedId = null;
    render();
  }
});
canvas.addEventListener("mousemove", (e) => {
  if (!dragging || !selectedId) return;
  const rect = canvas.getBoundingClientRect();
  const px = e.clientX - rect.left, py = e.clientY - rect.top;
  const layer = layers.find((l) => l.id === selectedId);
  if (layer) {
    layer.x = px - dragOffset.x;
    layer.y = py - dragOffset.y;
    render();
  }
});
window.addEventListener("mouseup", () => { dragging = false; });

saveBtn.addEventListener("click", () => {
  selectedId = null;
  render();
  const finalImage = canvas.toDataURL("image/jpeg", 0.92);
  window.dispatchEvent(new CustomEvent("image-edit-saved", { detail: { imageData: finalImage } }));
  closeEditor();
});

export function initImageEditor(onSaved) {
  onSaveCallback = onSaved;
  window.addEventListener("image-edit-saved", (e) => {
    onSaveCallback?.(e.detail.imageData);
  });
}