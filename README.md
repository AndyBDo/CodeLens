# CodeLens

Hover over any button in your running web app and press **Ctrl+Shift+E** to see an AI-powered panel explaining exactly what that button does — sourced entirely from your codebase.

CodeLens has two parts:

- **`backend/`** — a FastAPI server that indexes a GitHub or GitLab repository into a local ChromaDB vector store and runs a LangChain ReAct agent (Claude Sonnet 4.5) with read-only tools: `search_codebase`, `read_file` (GitHub/GitLab), plus optionally `search_docs` (Confluence) and `search_tickets` (Jira). CodeLens never reads your local files — it only sees the sources you give it: the repo, Confluence, and Jira.
- **`extension/`** — a Chrome extension (Manifest V3, plain JavaScript) that captures the hovered button and renders the explanation panel.

## Hotkeys

- **Ctrl+Shift+L** — open the setup menu: configure the GitHub or GitLab repository your web app comes from, plus optional Confluence (product/spec context) and Jira (known issues) integrations. Setup is required before analyzing — there is no local-file fallback.
- **Ctrl+Shift+E** — analyze the hovered button. Pressing the panel's **✕** while it's loading cancels the request and stops the backend analysis.

When Jira is configured, the agent searches for open tickets mentioning the button or its endpoint and shows a **Known Issues** section with its own assessment of what is likely broken, combining the ticket, Confluence docs, and the code. Everything is strictly read-only — the agent only ever performs GET requests.

## Prerequisites

- Python 3.11+
- pip
- Google Chrome
- An Anthropic API key (embeddings run locally with `all-MiniLM-L6-v2` — the key is only used for the LLM)

## Setup

### 1. Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Set your Anthropic API key

```bash
export ANTHROPIC_API_KEY=your_key_here
```

### 3. Start the backend

```bash
uvicorn main:app --reload --port 8000
```

### 4. Load the Chrome extension

1. Open `chrome://extensions`
2. Turn on **Developer mode** (top right)
3. Click **Load unpacked**
4. Select the `extension/` folder

### 5. Use it

1. Open `http://localhost:3000`
2. Press **Ctrl+Shift+L**, pick GitHub or GitLab, and configure your repo (plus optional Confluence and Jira). Saving indexes the code straight from the provider's API — this step is required; analysis is blocked until a repo is configured.
3. Hover over any button
4. Press **Ctrl+Shift+E**

For GitHub use a personal access token with repo read access; for GitLab use one with `read_api` scope. For Confluence/Jira (Atlassian Cloud) use your account email plus an API token from id.atlassian.com. Tokens are stored in `backend/config.json` (gitignored) and in Chrome extension storage for form prefill.

A panel appears next to the button with a summary, the endpoint it hits, the files involved, a step-by-step internal walkthrough, and relevant code snippets.

## Troubleshooting

**"Backend not reachable" error in the panel**
The FastAPI server isn't running. Start it with `uvicorn main:app --reload --port 8000` from the `backend/` folder and try again.

**CORS errors in the browser console**
The backend enables CORS for all origins, so this usually means an old server process is running. Stop any stale `uvicorn` processes and restart the backend.

**The button has no `data-testid`**
CodeLens still works — it falls back to the button's visible label and the current route. Results are best when buttons have `data-testid` attributes, since the agent can find the exact handler in the frontend code.

**Stale or wrong results after code changes**
The index is a snapshot. Re-index by pressing **Ctrl+Shift+L** and clicking **Save & Index** again, or delete `backend/chroma_db/` and restart the backend — it rebuilds automatically from the configured repo when the folder is missing.

**Nothing happens on Ctrl+Shift+E**
Make sure you're on `http://localhost:3000` (the extension only injects there), the cursor is over a `<button>` element when you press the hotkey, and the extension is loaded and enabled in `chrome://extensions`.
