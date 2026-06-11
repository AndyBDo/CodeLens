const CODELENS_BACKEND = "http://localhost:8000";

function showSetupMenu() {
  const existing = document.getElementById("codelens-setup");
  if (existing) {
    existing.remove();
    return;
  }

  const overlay = document.createElement("div");
  overlay.id = "codelens-setup";

  const menu = document.createElement("div");
  menu.className = "codelens-setup-menu";
  overlay.appendChild(menu);

  const closeBtn = document.createElement("button");
  closeBtn.className = "codelens-close";
  closeBtn.textContent = "✕";
  closeBtn.addEventListener("click", () => overlay.remove());
  menu.appendChild(closeBtn);

  const body = document.createElement("div");
  body.className = "codelens-body";
  menu.appendChild(body);

  const fields = {};

  function addSection(label, defs) {
    const section = document.createElement("div");
    section.className = "codelens-section";
    const labelEl = document.createElement("div");
    labelEl.className = "codelens-section-label";
    labelEl.textContent = label;
    section.appendChild(labelEl);
    for (const def of defs) {
      const input = document.createElement("input");
      input.className = "codelens-input";
      input.placeholder = def.placeholder;
      input.type = def.secret ? "password" : "text";
      if (def.value) input.value = def.value;
      fields[def.key] = input;
      section.appendChild(input);
    }
    body.appendChild(section);
  }

  const repoSection = document.createElement("div");
  repoSection.className = "codelens-section";
  const repoLabel = document.createElement("div");
  repoLabel.className = "codelens-section-label";
  repoLabel.textContent = "Repository (code source — required)";
  repoSection.appendChild(repoLabel);

  const providerSelect = document.createElement("select");
  providerSelect.className = "codelens-input";
  for (const [value, text] of [["github", "GitHub"], ["gitlab", "GitLab"]]) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = text;
    providerSelect.appendChild(option);
  }
  fields.repo_provider = providerSelect;
  repoSection.appendChild(providerSelect);

  const repoPlaceholders = {
    github: {
      repo_base: "Base URL (default: https://api.github.com)",
      repo_project: "Repository, e.g. andy/task-app (required)",
      repo_token: "Personal access token (repo read scope)",
    },
    gitlab: {
      repo_base: "Base URL (default: https://gitlab.com)",
      repo_project: "Project path, e.g. andy/task-app (required)",
      repo_token: "Personal access token (read_api scope)",
    },
  };

  for (const def of [
    { key: "repo_base" },
    { key: "repo_project" },
    { key: "repo_ref", placeholder: "Branch or tag (default: main)" },
    { key: "repo_token", secret: true },
  ]) {
    const input = document.createElement("input");
    input.className = "codelens-input";
    input.type = def.secret ? "password" : "text";
    input.placeholder = def.placeholder || repoPlaceholders.github[def.key];
    fields[def.key] = input;
    repoSection.appendChild(input);
  }

  providerSelect.addEventListener("change", () => {
    const placeholders = repoPlaceholders[providerSelect.value];
    for (const [key, text] of Object.entries(placeholders)) {
      fields[key].placeholder = text;
    }
  });

  body.appendChild(repoSection);

  addSection("Confluence (optional — extra context)", [
    { key: "cf_base", placeholder: "Base URL, e.g. https://yourorg.atlassian.net" },
    { key: "cf_email", placeholder: "Account email" },
    { key: "cf_token", placeholder: "API token", secret: true },
    { key: "cf_space", placeholder: "Space key (optional)" },
  ]);

  addSection("Jira (optional — known issues)", [
    { key: "jr_base", placeholder: "Base URL, e.g. https://yourorg.atlassian.net" },
    { key: "jr_email", placeholder: "Account email" },
    { key: "jr_token", placeholder: "API token", secret: true },
    { key: "jr_project", placeholder: "Project key, e.g. TASK (optional)" },
  ]);

  const status = document.createElement("div");
  status.className = "codelens-setup-status";
  body.appendChild(status);

  const saveBtn = document.createElement("button");
  saveBtn.className = "codelens-save";
  saveBtn.textContent = "Save & Index";
  saveBtn.addEventListener("click", () => saveSetup(fields, status, saveBtn));
  body.appendChild(saveBtn);

  document.body.appendChild(overlay);

  // chrome.storage throws "Extension context invalidated" if the extension
  // was reloaded after this content script was injected — skip prefill then.
  try {
    chrome.storage.local.get("codelensSetup", ({ codelensSetup }) => {
      if (!chrome.runtime.lastError && codelensSetup) {
        for (const [key, value] of Object.entries(codelensSetup)) {
          if (fields[key] && value) fields[key].value = value;
        }
        fields.repo_provider.dispatchEvent(new Event("change"));
      }
      prefillFromBackend(fields);
    });
  } catch (err) {
    prefillFromBackend(fields);
  }

  fetchStatus(status);
}

async function prefillFromBackend(fields) {
  // The backend's saved config is the source of truth: without this, a fresh
  // browser profile shows blank fields and saving would wipe the saved setup.
  let config;
  try {
    const res = await fetch(`${CODELENS_BACKEND}/config`);
    config = (await res.json()).config || {};
  } catch (err) {
    return;
  }

  const fill = (key, value) => {
    if (value && !fields[key].value) fields[key].value = value;
  };
  const markSavedToken = (key, hasToken) => {
    if (hasToken && !fields[key].value) {
      fields[key].placeholder = "Token saved — leave blank to keep it";
    }
  };

  const repo = config.github || config.gitlab;
  if (repo) {
    fields.repo_provider.value = config.github ? "github" : "gitlab";
    fields.repo_provider.dispatchEvent(new Event("change"));
    fill("repo_base", repo.base_url);
    fill("repo_project", repo.project);
    fill("repo_ref", repo.ref);
    markSavedToken("repo_token", repo.has_token);
  }
  if (config.confluence) {
    fill("cf_base", config.confluence.base_url);
    fill("cf_email", config.confluence.email);
    fill("cf_space", config.confluence.space);
    markSavedToken("cf_token", config.confluence.has_token);
  }
  if (config.jira) {
    fill("jr_base", config.jira.base_url);
    fill("jr_email", config.jira.email);
    fill("jr_project", config.jira.project);
    markSavedToken("jr_token", config.jira.has_token);
  }
}

async function fetchStatus(statusEl) {
  try {
    const res = await fetch(`${CODELENS_BACKEND}/status`);
    const data = await res.json();
    if (data.detail) setStatus(statusEl, data.state, data.detail);
  } catch (err) {
    setStatus(statusEl, "error", "Backend not reachable on port 8000.");
  }
}

function closeSetupSoon(statusEl) {
  // Let the user see the success status, then close the menu.
  setTimeout(() => {
    const overlay = document.getElementById("codelens-setup");
    if (overlay && overlay.contains(statusEl)) overlay.remove();
  }, 1200);
}

function setStatus(statusEl, state, text) {
  statusEl.textContent = text;
  statusEl.className = `codelens-setup-status codelens-setup-${state}`;
}

async function saveSetup(fields, statusEl, saveBtn) {
  const value = (key) => fields[key].value.trim();

  const provider = value("repo_provider");
  if (!value("repo_project")) {
    setStatus(statusEl, "error", "Repository path is required.");
    return;
  }

  const repo = {
    base_url: value("repo_base") || (provider === "github" ? "https://api.github.com" : "https://gitlab.com"),
    project: value("repo_project"),
    ref: value("repo_ref") || "main",
    token: value("repo_token"),
  };

  const payload = {
    github: provider === "github" ? repo : null,
    gitlab: provider === "gitlab" ? repo : null,
    confluence: value("cf_base")
      ? {
          base_url: value("cf_base"),
          email: value("cf_email"),
          token: value("cf_token"),
          space: value("cf_space"),
        }
      : null,
    jira: value("jr_base")
      ? {
          base_url: value("jr_base"),
          email: value("jr_email"),
          token: value("jr_token"),
          project: value("jr_project"),
        }
      : null,
  };

  const stored = {};
  for (const key of Object.keys(fields)) stored[key] = fields[key].value;
  try {
    chrome.storage.local.set({ codelensSetup: stored });
  } catch (err) {
    // Extension context invalidated — config still reaches the backend below;
    // only the local prefill cache is skipped.
  }

  saveBtn.disabled = true;
  setStatus(statusEl, "indexing", "Saving configuration...");

  try {
    const res = await fetch(`${CODELENS_BACKEND}/configure`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.index && data.index.state === "indexing") {
      setStatus(statusEl, "indexing", "Indexing repository...");
      pollUntilReady(statusEl, saveBtn);
      return;
    }
    setStatus(statusEl, data.index.state, data.index.detail || "Saved.");
    saveBtn.disabled = false;
    if (data.index.state === "ready") closeSetupSoon(statusEl);
  } catch (err) {
    setStatus(statusEl, "error", "Backend not reachable. Is the FastAPI server running on port 8000?");
    saveBtn.disabled = false;
  }
}

function pollUntilReady(statusEl, saveBtn) {
  const interval = setInterval(async () => {
    try {
      const res = await fetch(`${CODELENS_BACKEND}/status`);
      const data = await res.json();
      setStatus(statusEl, data.state, data.detail);
      if (data.state === "ready" || data.state === "error") {
        clearInterval(interval);
        saveBtn.disabled = false;
        if (data.state === "ready") closeSetupSoon(statusEl);
      }
    } catch (err) {
      clearInterval(interval);
      setStatus(statusEl, "error", "Lost connection to backend.");
      saveBtn.disabled = false;
    }
  }, 2000);
}
