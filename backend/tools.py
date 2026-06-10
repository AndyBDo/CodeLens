import re

import requests
from langchain_core.tools import tool

from config import get_config
from indexer import load_index

# All external calls in this module are read-only GET requests.

_vectorstore = None


def set_vectorstore(vectorstore):
    global _vectorstore
    _vectorstore = vectorstore


def _get_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = load_index()
    return _vectorstore


@tool
def search_codebase(query: str) -> str:
    """Search the indexed codebase for code relevant to the query.
    Returns the top 5 matching code chunks with their file paths."""
    results = _get_vectorstore().similarity_search(query, k=5)
    if not results:
        return "No results found in the codebase for this query."

    parts = []
    for i, doc in enumerate(results, 1):
        file_path = doc.metadata.get("file_path", "unknown")
        parts.append(f"--- Result {i} | File: {file_path} ---\n{doc.page_content}")
    return "\n\n".join(parts)


@tool
def read_file(file_path: str) -> str:
    """Read the full contents of a file from the indexed repository (GitHub or GitLab).
    Use this when a search result chunk is not enough context. Pass the file path
    exactly as shown in search_codebase results."""
    config = get_config()
    if (config.get("github") or {}).get("project"):
        from github_indexer import fetch_file

        repo = config["github"]
        default_base = "https://api.github.com"
    elif (config.get("gitlab") or {}).get("project"):
        from gitlab_indexer import fetch_file

        repo = config["gitlab"]
        default_base = "https://gitlab.com"
    else:
        return "No repository is configured; read_file is unavailable."
    try:
        content = fetch_file(
            repo.get("base_url") or default_base,
            repo.get("token", ""),
            repo["project"],
            repo.get("ref", "main"),
            file_path,
        )
    except requests.RequestException as e:
        return f"Could not read file '{file_path}': {e}"
    if len(content) > 8000:
        content = content[:8000] + "\n... [truncated]"
    return f"--- {file_path} ---\n{content}"


def _strip_html(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


@tool
def search_docs(query: str) -> str:
    """Search the Confluence documentation for pages relevant to the query.
    Returns page titles, excerpts, and links. Use this to understand the product
    intent, specs, or architecture behind a feature."""
    confluence = get_config().get("confluence") or {}
    base_url = confluence.get("base_url", "").rstrip("/")
    if not base_url:
        return "Confluence is not configured."

    space_filter = f' and space = "{confluence["space"]}"' if confluence.get("space") else ""

    # CQL `text ~ "..."` is an exact-phrase match, so multi-word agent queries
    # like "add task button" often miss. Try the phrase first, then fall back
    # to OR-ing the individual words.
    words = [w for w in query.replace('"', "").split() if w]
    candidates = [f'text ~ "{query}"' + space_filter]
    if len(words) > 1:
        per_word = " or ".join(f'text ~ "{w}"' for w in words)
        candidates.append(f"({per_word})" + space_filter)

    results = []
    try:
        for cql in candidates:
            response = requests.get(
                f"{base_url}/wiki/rest/api/content/search",
                params={"cql": cql, "limit": 3, "expand": "body.storage"},
                auth=(confluence.get("email", ""), confluence.get("token", "")),
                timeout=30,
            )
            response.raise_for_status()
            results = response.json().get("results", [])
            if results:
                break
    except requests.RequestException as e:
        return f"Confluence search failed: {e}"

    if not results:
        return "No Confluence pages found for this query."

    parts = []
    for page in results:
        title = page.get("title", "Untitled")
        link = f"{base_url}/wiki{page.get('_links', {}).get('webui', '')}"
        body = _strip_html(page.get("body", {}).get("storage", {}).get("value", ""))[:800]
        parts.append(f"--- Page: {title} | Link: {link} ---\n{body}")
    return "\n\n".join(parts)


@tool
def search_tickets(query: str) -> str:
    """Search Jira for tickets mentioning the query. Returns key, summary, status,
    priority, and link for each ticket. Use this to find known bugs or open work
    related to a button or feature."""
    jira = get_config().get("jira") or {}
    base_url = jira.get("base_url", "").rstrip("/")
    if not base_url:
        return "Jira is not configured."

    jql = f'text ~ "{query}"'
    if jira.get("project"):
        jql += f' and project = "{jira["project"]}"'
    jql += " order by updated desc"

    try:
        response = requests.get(
            f"{base_url}/rest/api/3/search/jql",
            params={"jql": jql, "maxResults": 5, "fields": "summary,status,priority,issuetype"},
            auth=(jira.get("email", ""), jira.get("token", "")),
            timeout=30,
        )
        if response.status_code == 404:
            response = requests.get(
                f"{base_url}/rest/api/3/search",
                params={"jql": jql, "maxResults": 5, "fields": "summary,status,priority,issuetype"},
                auth=(jira.get("email", ""), jira.get("token", "")),
                timeout=30,
            )
        response.raise_for_status()
        issues = response.json().get("issues", [])
    except requests.RequestException as e:
        return f"Jira search failed: {e}"

    if not issues:
        return "No Jira tickets found for this query."

    parts = []
    for issue in issues:
        fields = issue.get("fields", {})
        key = issue.get("key", "")
        status = (fields.get("status") or {}).get("name", "Unknown")
        priority = (fields.get("priority") or {}).get("name", "Unknown")
        issue_type = (fields.get("issuetype") or {}).get("name", "Issue")
        parts.append(
            f"- {key} [{issue_type} | {status} | {priority}]: {fields.get('summary', '')} "
            f"| Link: {base_url}/browse/{key}"
        )
    return "\n".join(parts)


def get_active_tools():
    config = get_config()
    active = [search_codebase]
    if (config.get("github") or {}).get("project") or (config.get("gitlab") or {}).get("project"):
        active.append(read_file)
    if (config.get("confluence") or {}).get("base_url"):
        active.append(search_docs)
    if (config.get("jira") or {}).get("base_url"):
        active.append(search_tickets)
    return active
