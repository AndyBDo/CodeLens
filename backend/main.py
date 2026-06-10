import os
import threading
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import tools
from agent import analyze_button, request_cancel, reset_executor
from config import get_config, load_config, save_config
from github_indexer import build_github_index
from gitlab_indexer import build_gitlab_index
from indexer import PERSIST_DIR, load_index

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

app = FastAPI(title="CodeLens Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# The backend never indexes local files: code only comes from the configured
# GitHub/GitLab repo, plus optional Confluence and Jira.
index_status = {"state": "unconfigured", "detail": "Run setup (Ctrl+Shift+L) to connect a repository."}


class AnalyzeRequest(BaseModel):
    testid: str
    label: str
    route: str
    request_id: str = ""
    html: str = ""
    surrounding_text: str = ""


class CancelRequest(BaseModel):
    request_id: str


class RepoConfig(BaseModel):
    base_url: str = ""
    project: str
    ref: str = "main"
    token: str = ""


class ConfluenceConfig(BaseModel):
    base_url: str
    email: str = ""
    token: str = ""
    space: str = ""


class JiraConfig(BaseModel):
    base_url: str
    email: str = ""
    token: str = ""
    project: str = ""


class ConfigureRequest(BaseModel):
    github: RepoConfig | None = None
    gitlab: RepoConfig | None = None
    confluence: ConfluenceConfig | None = None
    jira: JiraConfig | None = None


def _site_root(url: str) -> str:
    """Reduce a pasted Confluence/Jira link (board, backlog, wiki page) to the site root."""
    url = (url or "").strip()
    if not url:
        return url
    if "://" not in url:
        url = f"https://{url}"
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _configured_repo(config: dict):
    """Returns (provider, repo_config) or (None, None)."""
    for provider in ("github", "gitlab"):
        repo = config.get(provider) or {}
        if repo.get("project"):
            return provider, repo
    return None, None


def _index_repo_in_background(provider: str, repo: dict):
    global index_status
    label = f"{repo['project']}@{repo.get('ref', 'main')}"
    index_status = {"state": "indexing", "detail": f"Indexing {label} ({provider})..."}
    try:
        build = build_github_index if provider == "github" else build_gitlab_index
        default_base = "https://api.github.com" if provider == "github" else "https://gitlab.com"
        vectorstore = build(
            repo.get("base_url") or default_base,
            repo.get("token", ""),
            repo["project"],
            repo.get("ref", "main"),
        )
        tools.set_vectorstore(vectorstore)
        index_status = {"state": "ready", "detail": f"Indexed {label} ({provider})"}
    except Exception as e:
        index_status = {"state": "error", "detail": f"{provider} indexing failed: {e}"}


@app.on_event("startup")
def startup():
    global index_status
    load_config()
    provider, repo = _configured_repo(get_config())
    if not provider:
        return
    if os.path.exists(PERSIST_DIR):
        print(f"Loading existing index from {PERSIST_DIR}")
        tools.set_vectorstore(load_index())
        index_status = {
            "state": "ready",
            "detail": f"Loaded existing index ({repo['project']}@{repo.get('ref', 'main')})",
        }
    else:
        print(f"No existing index found. Re-indexing configured {provider} repo: {repo['project']}")
        threading.Thread(target=_index_repo_in_background, args=(provider, repo), daemon=True).start()


@app.get("/config")
def read_config():
    config = get_config()
    safe = {}
    for section in ("github", "gitlab", "confluence", "jira"):
        if config.get(section):
            safe[section] = {k: v for k, v in config[section].items() if k != "token"}
            safe[section]["has_token"] = bool(config[section].get("token"))
    return {"config": safe, "index": index_status}


@app.get("/status")
def status():
    return index_status


@app.post("/configure")
def configure(request: ConfigureRequest):
    old_provider, old_repo = _configured_repo(get_config())
    config = {
        "github": request.github.model_dump() if request.github else None,
        "gitlab": request.gitlab.model_dump() if request.gitlab else None,
        "confluence": request.confluence.model_dump() if request.confluence else None,
        "jira": request.jira.model_dump() if request.jira else None,
    }
    for section in ("confluence", "jira"):
        if config[section]:
            config[section]["base_url"] = _site_root(config[section]["base_url"])
    # A blank token field means "keep the saved one" — the UI never echoes secrets back.
    old_config = get_config()
    for section in ("github", "gitlab", "confluence", "jira"):
        old = old_config.get(section) or {}
        if config[section] and not config[section].get("token") and old.get("token"):
            config[section]["token"] = old["token"]
    save_config(config)
    reset_executor()

    provider, repo = _configured_repo(config)
    if not provider:
        return {"ok": False, "index": {"state": "error", "detail": "A GitHub or GitLab repository is required."}}

    old_repo = old_repo or {}
    repo_changed = (
        provider != old_provider
        or old_repo.get("project") != repo["project"]
        or old_repo.get("ref") != repo["ref"]
        or old_repo.get("base_url") != repo["base_url"]
    )
    if repo_changed or index_status["state"] != "ready":
        threading.Thread(target=_index_repo_in_background, args=(provider, repo), daemon=True).start()
        return {"ok": True, "index": {"state": "indexing", "detail": "Indexing started"}}

    return {"ok": True, "index": index_status}


@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY is not set on the backend. Export it and restart uvicorn."}
    if index_status["state"] == "unconfigured":
        return {"error": "CodeLens is not set up yet. Press Ctrl+Shift+L to connect a GitHub or GitLab repository first."}
    if index_status["state"] == "indexing":
        return {"error": "Still indexing the repository — try again in a moment."}
    if index_status["state"] == "error":
        return {"error": index_status["detail"]}
    return analyze_button(
        request.testid,
        request.label,
        request.route,
        request.request_id,
        request.html,
        request.surrounding_text,
    )


@app.post("/cancel")
def cancel(request: CancelRequest):
    request_cancel(request.request_id)
    return {"ok": True}
