(function () {
  "use strict";

  const fileInput = document.getElementById("fileInput");
  const dropzone = document.getElementById("dropzone");
  const pasteInput = document.getElementById("pasteInput");
  const parseBtn = document.getElementById("parseBtn");
  const clearBtn = document.getElementById("clearBtn");
  const wrapToggle = document.getElementById("wrapToggle");
  const newlineToggle = document.getElementById("newlineToggle");
  const output = document.getElementById("output");
  const stats = document.getElementById("stats");
  const errorBox = document.getElementById("errorBox");

  // Remember the last processed text so toggles can re-render without re-reading.
  let lastText = "";

  // --- Syntax highlighting -------------------------------------------------
  function escapeHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  // Convert escaped newline sequences inside a string value into real newlines
  // so they render across multiple lines (white-space: pre is set on the body).
  function expandNewlines(match) {
    return match
      .replace(/\\r\\n/g, "\n")
      .replace(/\\r/g, "\n")
      .replace(/\\n/g, "\n");
  }

  // Highlight JSON string produced by JSON.stringify with indentation.
  // When expandNl is true, \n escapes inside string values become real line breaks.
  function highlight(json, expandNl) {
    const escaped = escapeHtml(json);
    return escaped.replace(
      /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g,
      function (match) {
        let cls = "number";
        let content = match;
        if (/^"/.test(match)) {
          if (/:$/.test(match)) {
            cls = "key";
          } else {
            cls = "string";
            if (expandNl) {
              content = expandNewlines(content);
            }
          }
        } else if (/true|false/.test(match)) {
          cls = "boolean";
        } else if (/null/.test(match)) {
          cls = "null";
        }
        return '<span class="' + cls + '">' + content + "</span>";
      }
    );
  }

  // --- Parsing -------------------------------------------------------------
  function parseJsonl(text) {
    const lines = text.split(/\r?\n/);
    const records = [];
    const errors = [];
    lines.forEach(function (line, i) {
      const trimmed = line.trim();
      if (trimmed === "") return; // skip blank lines
      try {
        records.push({ index: i + 1, value: JSON.parse(trimmed), raw: trimmed });
      } catch (e) {
        errors.push({ line: i + 1, message: e.message, raw: trimmed });
      }
    });
    return { records: records, errors: errors };
  }

  // --- Rendering -----------------------------------------------------------
  function render(records, errors) {
    const expandNl = newlineToggle.checked;
    output.innerHTML = "";
    errorBox.hidden = true;
    errorBox.textContent = "";

    if (errors.length) {
      errorBox.hidden = false;
      errorBox.textContent =
        errors.length + " line(s) could not be parsed: " +
        errors
          .map(function (e) { return "line " + e.line + " (" + e.message + ")"; })
          .join(", ");
    }

    if (records.length === 0 && errors.length === 0) {
      output.innerHTML = '<div class="empty">No records yet — load a file or paste JSONL and hit Pretty Print.</div>';
      stats.textContent = "";
      return;
    }

    stats.textContent = records.length
      ? records.length + " record" + (records.length === 1 ? "" : "s") + " parsed"
      : "0 records parsed";

    records.forEach(function (rec) {
      const card = document.createElement("div");
      card.className = "record";

      const head = document.createElement("div");
      head.className = "record-head";
      const idx = document.createElement("span");
      idx.className = "index";
      idx.textContent = "#" + rec.index;
      const label = document.createElement("span");
      label.textContent = "Line " + rec.index;
      head.appendChild(idx);
      head.appendChild(label);

      const copyBtn = document.createElement("button");
      copyBtn.className = "copy";
      copyBtn.textContent = "Copy";
      copyBtn.addEventListener("click", function () {
        navigator.clipboard.writeText(JSON.stringify(rec.value, null, 2));
        copyBtn.textContent = "Copied!";
        setTimeout(function () { copyBtn.textContent = "Copy"; }, 1200);
      });
      head.appendChild(copyBtn);

      const body = document.createElement("div");
      body.className = "record-body";
      body.innerHTML = highlight(JSON.stringify(rec.value, null, 2), expandNl);

      card.appendChild(head);
      card.appendChild(body);
      output.appendChild(card);
    });
  }

  function process(text) {
    lastText = text;
    const result = parseJsonl(text);
    render(result.records, result.errors);
  }

  function reprocess() {
    const result = parseJsonl(lastText);
    render(result.records, result.errors);
  }

  // --- Events --------------------------------------------------------------
  function handleFile(file) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = function (e) {
      pasteInput.value = e.target.result;
      process(e.target.result);
    };
    reader.onerror = function () {
      errorBox.hidden = false;
      errorBox.textContent = "Could not read file: " + reader.error;
    };
    reader.readAsText(file);
  }

  dropzone.addEventListener("click", function () { fileInput.click(); });
  fileInput.addEventListener("change", function () { handleFile(fileInput.files[0]); });

  ["dragenter", "dragover"].forEach(function (evt) {
    dropzone.addEventListener(evt, function (e) {
      e.preventDefault();
      dropzone.classList.add("drag");
    });
  });
  ["dragleave", "drop"].forEach(function (evt) {
    dropzone.addEventListener(evt, function (e) {
      e.preventDefault();
      dropzone.classList.remove("drag");
    });
  });
  dropzone.addEventListener("drop", function (e) {
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  });

  parseBtn.addEventListener("click", function () { process(pasteInput.value); });
  pasteInput.addEventListener("input", function () { process(pasteInput.value); });

  clearBtn.addEventListener("click", function () {
    pasteInput.value = "";
    fileInput.value = "";
    lastText = "";
    output.innerHTML = "";
    stats.textContent = "";
    errorBox.hidden = true;
    render([], []);
  });

  wrapToggle.addEventListener("change", function () {
    document.body.classList.toggle("wrap", wrapToggle.checked);
  });

  newlineToggle.addEventListener("change", function () {
    reprocess();
  });

  // Initial empty state
  render([], []);
})();