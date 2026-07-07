(function () {
  "use strict";

  function formatBytes(bytes) {
    if (bytes < 1024) return bytes + " B";
    const units = ["KB", "MB", "GB"];
    let value = bytes;
    let unit = -1;
    do {
      value /= 1024;
      unit += 1;
    } while (value >= 1024 && unit < units.length - 1);
    return value.toFixed(1) + " " + units[unit];
  }

  function setupUploadForm() {
    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input");
    const fileInfo = document.getElementById("file-info");
    const translationCheckbox = document.getElementById("translation_enabled");
    const translationFields = document.getElementById("translation-fields");
    const form = document.getElementById("upload-form");
    const submitButton = document.getElementById("submit-button");

    if (!dropZone || !fileInput) return;

    function showFileInfo() {
      const file = fileInput.files[0];
      if (!file) {
        fileInfo.textContent = "";
        return;
      }
      fileInfo.textContent = file.name + " — " + formatBytes(file.size);
    }

    fileInput.addEventListener("change", showFileInfo);

    ["dragenter", "dragover"].forEach((evt) =>
      dropZone.addEventListener(evt, (e) => {
        e.preventDefault();
        dropZone.classList.add("dragover");
      })
    );
    ["dragleave", "drop"].forEach((evt) =>
      dropZone.addEventListener(evt, (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
      })
    );
    dropZone.addEventListener("drop", (e) => {
      const files = e.dataTransfer.files;
      if (files && files.length > 0) {
        fileInput.files = files;
        showFileInfo();
      }
    });

    function toggleTranslationFields() {
      const enabled = translationCheckbox.checked;
      translationFields.classList.toggle("enabled", enabled);
      translationFields.querySelectorAll("select, input").forEach((el) => {
        el.disabled = !enabled;
      });
    }
    if (translationCheckbox) {
      translationCheckbox.addEventListener("change", toggleTranslationFields);
      toggleTranslationFields();
    }

    if (form) {
      form.addEventListener("submit", () => {
        submitButton.disabled = true;
        submitButton.textContent = "Subiendo…";
      });
    }
  }

  function pollJobStatus(jobId) {
    const statusLabel = document.getElementById("status-label");
    const statusMessage = document.getElementById("status-message");
    const progressFill = document.getElementById("progress-fill");
    const errorBox = document.getElementById("error-box");
    const resultBox = document.getElementById("result-box");
    const downloadLinks = document.getElementById("download-links");
    const previewBox = document.getElementById("preview-box");
    const previewFrame = document.getElementById("preview-frame");

    let stopped = false;

    async function tick() {
      if (stopped) return;
      try {
        const res = await fetch("/api/jobs/" + jobId + "/status");
        if (!res.ok) throw new Error("status " + res.status);
        const data = await res.json();

        statusLabel.textContent = data.status;
        if (data.total > 0) {
          progressFill.style.width = Math.round((100 * data.current) / data.total) + "%";
        }
        statusMessage.textContent = data.stage ? "[" + data.stage + "] " + (data.message || "") : "";

        if (data.status === "done") {
          stopped = true;
          resultBox.hidden = false;
          downloadLinks.innerHTML = "";
          data.output_formats.forEach((fmt) => {
            const li = document.createElement("li");
            const a = document.createElement("a");
            a.href = "/api/jobs/" + jobId + "/download/" + fmt;
            a.textContent = "Descargar " + fmt.toUpperCase();
            li.appendChild(a);
            downloadLinks.appendChild(li);
          });
          if (data.output_formats.includes("html")) {
            previewBox.hidden = false;
            previewFrame.src = "/api/jobs/" + jobId + "/preview";
          }
          return;
        }

        if (data.status === "error") {
          stopped = true;
          errorBox.hidden = false;
          errorBox.textContent = data.error || "El procesamiento falló por un motivo desconocido.";
          return;
        }
      } catch (err) {
        statusMessage.textContent = "No se pudo consultar el estado (reintentando…)";
      }
      setTimeout(tick, 2500);
    }

    tick();
  }

  document.addEventListener("DOMContentLoaded", setupUploadForm);
  window.ocrbook = { pollJobStatus: pollJobStatus };
})();
