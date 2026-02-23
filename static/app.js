(() => {
  "use strict";

  const $ = (s) => document.querySelector(s);

  // --- State ---
  let currentFile = null;
  let currentFilename = "";
  let originalMetadata = {};
  let editedMetadata = {};
  let isEditing = false;
  let hasChanges = false;

  const READONLY_TAGS = new Set([
    "SourceFile", "Directory", "FileName", "FileSize",
    "FileModifyDate", "FileAccessDate", "FileInodeChangeDate",
    "FilePermissions", "FileType", "FileTypeExtension",
    "MIMEType", "ExifToolVersion", "ExifByteOrder",
    "EncodingProcess", "BitsPerSample", "ColorComponents",
    "YCbCrSubSampling", "ImageWidth", "ImageHeight",
    "ImageSize", "Megapixels",
  ]);

  // --- DOM refs ---
  const dropzone = $("#dropzone");
  const fileInput = $("#file-input");
  const uploadView = $("#upload-view");
  const resultsView = $("#results-view");
  const filenameEl = $("#filename");
  const metadataContainer = $("#metadata-container");
  const viewActions = $("#view-actions");
  const editActions = $("#edit-actions");
  const loadingEl = $("#loading");
  const errorToast = $("#error-toast");
  const errorMsg = $("#error-msg");
  const saveFileBtn = $("#save-file-btn");

  // --- Upload handlers ---
  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fileInput.click();
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length) handleFile(e.target.files[0]);
  });

  // Drag and drop
  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });
  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
  });
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
  });

  // --- Core: upload and extract ---
  async function handleFile(file) {
    currentFile = file;
    showLoading();

    const form = new FormData();
    form.append("file", file);

    try {
      const res = await fetch("/api/extract", { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Error al extraer metadatos.");

      originalMetadata = data.metadata;
      editedMetadata = { ...data.metadata };
      currentFilename = data.filename;
      filenameEl.textContent = currentFilename;

      isEditing = false;
      hasChanges = false;
      renderMetadata(false);
      showView("results");
    } catch (err) {
      showError(err.message);
      showView("upload");
    } finally {
      hideLoading();
    }
  }

  // --- Render metadata rows ---
  function renderMetadata(editable) {
    metadataContainer.replaceChildren();
    const entries = Object.entries(editable ? editedMetadata : originalMetadata);

    if (entries.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "No se encontraron metadatos en este archivo.";
      metadataContainer.appendChild(empty);
      return;
    }

    for (const [key, value] of entries) {
      const row = document.createElement("div");
      row.className = "meta-row";

      const keyEl = document.createElement("div");
      keyEl.className = "meta-key";
      keyEl.textContent = key;

      const valueEl = document.createElement("div");
      valueEl.className = "meta-value";

      if (editable && !READONLY_TAGS.has(key)) {
        const input = document.createElement("input");
        input.type = "text";
        input.className = "meta-input";
        input.value = String(value ?? "");
        input.dataset.key = key;
        input.addEventListener("input", () => {
          editedMetadata[key] = input.value;
          const modified = String(originalMetadata[key] ?? "") !== input.value;
          row.classList.toggle("modified", modified);
          checkChanges();
        });
        valueEl.appendChild(input);
      } else {
        valueEl.textContent = String(value ?? "");
        if (READONLY_TAGS.has(key) && editable) {
          row.classList.add("readonly");
        }
      }

      row.appendChild(keyEl);
      row.appendChild(valueEl);
      metadataContainer.appendChild(row);
    }
  }

  function checkChanges() {
    hasChanges = Object.keys(originalMetadata).some(
      (k) => String(originalMetadata[k] ?? "") !== String(editedMetadata[k] ?? "")
    );
    saveFileBtn.disabled = !hasChanges;
  }

  // --- View switching ---
  function showView(view) {
    uploadView.hidden = view !== "upload";
    resultsView.hidden = view !== "results";
    if (view === "results") {
      viewActions.hidden = isEditing;
      editActions.hidden = !isEditing;
    }
    if (view === "upload") {
      fileInput.value = "";
    }
  }

  // --- Edit mode ---
  $("#edit-btn").addEventListener("click", () => {
    isEditing = true;
    editedMetadata = { ...originalMetadata };
    hasChanges = false;
    saveFileBtn.disabled = true;
    renderMetadata(true);
    showView("results");
  });

  $("#cancel-edit-btn").addEventListener("click", () => {
    isEditing = false;
    hasChanges = false;
    renderMetadata(false);
    showView("results");
  });

  // --- New file ---
  $("#new-btn").addEventListener("click", () => {
    currentFile = null;
    currentFilename = "";
    originalMetadata = {};
    editedMetadata = {};
    isEditing = false;
    hasChanges = false;
    showView("upload");
  });

  // --- Download JSON (client-side) ---
  function downloadJson() {
    const data = isEditing ? editedMetadata : originalMetadata;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const stem = currentFilename.replace(/\.[^.]+$/, "") || "archivo";
    a.download = stem + "_metadata.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  $("#download-json-btn").addEventListener("click", downloadJson);
  $("#save-json-btn").addEventListener("click", downloadJson);

  // --- Download modified file (via server) ---
  $("#save-file-btn").addEventListener("click", async () => {
    if (!currentFile || !hasChanges) return;

    showLoading();

    const changes = {};
    for (const key of Object.keys(editedMetadata)) {
      if (String(originalMetadata[key] ?? "") !== String(editedMetadata[key] ?? "")) {
        changes[key] = editedMetadata[key];
      }
    }

    const form = new FormData();
    form.append("file", currentFile);
    form.append("metadata", JSON.stringify(changes));

    try {
      const res = await fetch("/api/modify", { method: "POST", body: form });
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "Error al modificar archivo.");
      }

      if (data.applied.length === 0) {
        showError("No se pudo modificar ningún campo. Los campos seleccionados no son escribibles para este tipo de archivo.");
        return;
      }

      // Download the file from base64
      const byteChars = atob(data.file);
      const byteArray = new Uint8Array(byteChars.length);
      for (let i = 0; i < byteChars.length; i++) {
        byteArray[i] = byteChars.charCodeAt(i);
      }
      const blob = new Blob([byteArray], { type: "application/octet-stream" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const ext = currentFilename.match(/\.[^.]+$/)?.[0] || "";
      const stem = currentFilename.replace(/\.[^.]+$/, "") || "archivo";
      a.download = stem + "_modified" + ext;
      a.click();
      URL.revokeObjectURL(url);

      // Show feedback
      if (data.failed.length > 0) {
        showWarning(
          data.applied.length + " campo(s) modificado(s). " +
          data.failed.length + " campo(s) no se pudieron escribir: " +
          data.failed.join(", ")
        );
      } else {
        showSuccess(data.applied.length + " campo(s) modificado(s) correctamente.");
      }
    } catch (err) {
      showError(err.message);
    } finally {
      hideLoading();
    }
  });

  // --- Loading ---
  function showLoading() { loadingEl.hidden = false; }
  function hideLoading() { loadingEl.hidden = true; }

  // --- Toast notifications ---
  let toastTimer = null;
  function showToast(msg, type) {
    errorMsg.textContent = msg;
    errorToast.hidden = false;
    errorToast.dataset.type = type;
    clearTimeout(toastTimer);
    const delay = type === "error" ? 8000 : 5000;
    toastTimer = setTimeout(() => { errorToast.hidden = true; }, delay);
  }

  function showError(msg) { showToast(msg, "error"); }
  function showWarning(msg) { showToast(msg, "warning"); }
  function showSuccess(msg) { showToast(msg, "success"); }

  $("#dismiss-error").addEventListener("click", () => {
    errorToast.hidden = true;
    clearTimeout(toastTimer);
  });
})();
