function showPanel(button, data, isLoading, onClose) {
  const existing = document.getElementById("codelens-panel");
  if (existing) existing.remove();

  const panel = document.createElement("div");
  panel.id = "codelens-panel";

  const header = document.createElement("div");
  header.className = "codelens-header";

  const title = document.createElement("span");
  title.className = "codelens-title";
  title.textContent = "CodeLens";
  header.appendChild(title);

  const closeBtn = document.createElement("button");
  closeBtn.className = "codelens-close";
  closeBtn.textContent = "✕";
  closeBtn.addEventListener("click", () => {
    if (onClose) onClose();
    panel.remove();
  });
  header.appendChild(closeBtn);

  panel.appendChild(header);

  const body = document.createElement("div");
  body.className = "codelens-body";
  panel.appendChild(body);

  if (isLoading) {
    const loading = document.createElement("div");
    loading.className = "codelens-loading";
    loading.textContent = "Analyzing codebase...";
    body.appendChild(loading);
  } else if (data && data.error) {
    if (data.summary) {
      body.appendChild(makeSection("Summary", textNode(data.summary)));
    }
    const error = document.createElement("div");
    error.className = "codelens-error";
    error.textContent = data.error;
    body.appendChild(error);
  } else if (data) {
    if (data.summary) {
      body.appendChild(makeSection("Summary", textNode(data.summary)));
    }

    if (data.endpoint) {
      body.appendChild(makeSection("Endpoint", makeEndpoint(data.endpoint)));
    }

    if (Array.isArray(data.files) && data.files.length > 0) {
      body.appendChild(makeSection("Files Involved", makeFileList(data.files)));
    }

    if (data.low_level) {
      body.appendChild(
        makeSection("What Happens Internally", makeSteps(data.low_level))
      );
    }

    if (Array.isArray(data.docs) && data.docs.length > 0) {
      body.appendChild(makeSection("Docs", makeDocs(data.docs)));
    }

    if (Array.isArray(data.known_issues) && data.known_issues.length > 0) {
      body.appendChild(
        makeSection("⚠ Known Issues", makeIssues(data.known_issues))
      );
    }

    if (Array.isArray(data.code_snippets) && data.code_snippets.length > 0) {
      body.appendChild(
        makeSection("Code Snippets", makeSnippets(data.code_snippets))
      );
    }
  }

  document.body.appendChild(panel);
  positionPanel(panel, button);
}

function positionPanel(panel, button) {
  const rect = button.getBoundingClientRect();
  const panelWidth = panel.offsetWidth || 440;
  const panelHeight = panel.offsetHeight;
  const gap = 12;

  // Prefer the right side of the button, fall back to the left.
  let left = rect.right + gap;
  if (left + panelWidth > window.innerWidth - gap) {
    left = rect.left - gap - panelWidth;
  }
  left = Math.max(gap, Math.min(left, window.innerWidth - panelWidth - gap));

  // Align with the button top, but keep the whole panel inside the viewport.
  let top = rect.top;
  top = Math.max(gap, Math.min(top, window.innerHeight - panelHeight - gap));

  panel.style.left = `${left}px`;
  panel.style.top = `${top}px`;
}

function textNode(text) {
  const p = document.createElement("p");
  p.className = "codelens-text";
  p.textContent = text;
  return p;
}

function makeSection(label, contentEl) {
  const section = document.createElement("div");
  section.className = "codelens-section";

  const labelEl = document.createElement("div");
  labelEl.className = "codelens-section-label";
  labelEl.textContent = label;

  section.appendChild(labelEl);
  section.appendChild(contentEl);
  return section;
}

function makeEndpoint(endpoint) {
  const container = document.createElement("div");
  container.className = "codelens-endpoint";

  const parts = endpoint.trim().split(/\s+/);
  const method = parts[0] ? parts[0].toUpperCase() : "";
  const path = parts.slice(1).join(" ");
  const knownMethods = ["GET", "POST", "PUT", "DELETE", "PATCH"];

  if (knownMethods.includes(method)) {
    const badge = document.createElement("span");
    badge.className = `codelens-badge codelens-badge-${method.toLowerCase()}`;
    badge.textContent = method;
    container.appendChild(badge);

    const pathEl = document.createElement("span");
    pathEl.className = "codelens-endpoint-path";
    pathEl.textContent = path;
    container.appendChild(pathEl);
  } else {
    const pathEl = document.createElement("span");
    pathEl.className = "codelens-endpoint-path";
    pathEl.textContent = endpoint;
    container.appendChild(pathEl);
  }
  return container;
}

function makeFileList(files) {
  const list = document.createElement("ul");
  list.className = "codelens-files";
  for (const file of files) {
    const item = document.createElement("li");
    item.className = "codelens-file";
    item.textContent = `📄 ${file}`;
    list.appendChild(item);
  }
  return list;
}

function makeSteps(lowLevel) {
  let steps = lowLevel
    .split(/\n+/)
    .map((s) => s.trim())
    .filter(Boolean);

  if (steps.length <= 1) {
    steps = lowLevel
      .split(/(?<=\.)\s+/)
      .map((s) => s.trim())
      .filter(Boolean);
  }

  const list = document.createElement("ol");
  list.className = "codelens-steps";
  for (const step of steps) {
    const item = document.createElement("li");
    item.textContent = step.replace(/^\d+[.)]\s*/, "");
    list.appendChild(item);
  }
  return list;
}

function makeDocs(docs) {
  const container = document.createElement("div");
  container.className = "codelens-docs";
  for (const doc of docs) {
    const item = document.createElement("div");
    item.className = "codelens-doc";

    const link = document.createElement("a");
    link.className = "codelens-doc-link";
    link.textContent = `📖 ${doc.title || "Documentation"}`;
    if (doc.link) {
      link.href = doc.link;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
    }
    item.appendChild(link);

    if (doc.note) {
      const note = document.createElement("div");
      note.className = "codelens-doc-note";
      note.textContent = doc.note;
      item.appendChild(note);
    }
    container.appendChild(item);
  }
  return container;
}

function makeIssues(issues) {
  const container = document.createElement("div");
  container.className = "codelens-issues";
  for (const issue of issues) {
    const card = document.createElement("div");
    card.className = "codelens-issue";

    const header = document.createElement("div");
    header.className = "codelens-issue-header";

    const key = document.createElement("a");
    key.className = "codelens-issue-key";
    key.textContent = issue.key || "TICKET";
    if (issue.link) {
      key.href = issue.link;
      key.target = "_blank";
      key.rel = "noopener noreferrer";
    }
    header.appendChild(key);

    if (issue.status) {
      const status = document.createElement("span");
      status.className = "codelens-issue-status";
      status.textContent = issue.status;
      header.appendChild(status);
    }
    card.appendChild(header);

    if (issue.summary) {
      const summary = document.createElement("div");
      summary.className = "codelens-issue-summary";
      summary.textContent = issue.summary;
      card.appendChild(summary);
    }

    if (issue.assessment) {
      const assessment = document.createElement("div");
      assessment.className = "codelens-issue-assessment";
      assessment.textContent = issue.assessment;
      card.appendChild(assessment);
    }
    container.appendChild(card);
  }
  return container;
}

function makeSnippets(snippets) {
  const container = document.createElement("div");
  container.className = "codelens-snippets";

  for (const snippet of snippets) {
    const block = document.createElement("div");
    block.className = "codelens-snippet";

    const fileBar = document.createElement("div");
    fileBar.className = "codelens-snippet-file";
    fileBar.textContent = snippet.file || "";
    block.appendChild(fileBar);

    const pre = document.createElement("pre");
    pre.className = "codelens-snippet-code";
    const code = document.createElement("code");
    code.textContent = snippet.code || "";
    pre.appendChild(code);
    block.appendChild(pre);

    if (snippet.explanation) {
      const explanation = document.createElement("div");
      explanation.className = "codelens-snippet-explanation";
      explanation.textContent = snippet.explanation;
      block.appendChild(explanation);
    }

    container.appendChild(block);
  }
  return container;
}
