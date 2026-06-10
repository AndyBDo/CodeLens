import requests

from indexer import INDEXED_EXTENSIONS, build_index_from_documents

# Read-only: only GET requests are ever made against the GitHub API.


def _api_base(base_url: str) -> str:
    base_url = (base_url or "").rstrip("/")
    # Anything on github.com (including a pasted repo URL) uses the public API.
    if not base_url or "github.com" in base_url:
        return "https://api.github.com"
    if base_url.endswith("/api/v3"):
        return base_url
    # GitHub Enterprise: https://ghe.example.com -> https://ghe.example.com/api/v3
    return f"{base_url}/api/v3"


def _headers(token: str) -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def list_repo_files(base_url: str, token: str, project: str, ref: str) -> list[str]:
    project = project.strip().strip("/")
    response = requests.get(
        f"{_api_base(base_url)}/repos/{project}/git/trees/{ref}",
        headers=_headers(token),
        params={"recursive": "1"},
        timeout=30,
    )
    response.raise_for_status()
    return [
        item["path"]
        for item in response.json().get("tree", [])
        if item.get("type") == "blob" and item["path"].endswith(INDEXED_EXTENSIONS)
    ]


def fetch_file(base_url: str, token: str, project: str, ref: str, file_path: str) -> str:
    project = project.strip().strip("/")
    headers = _headers(token)
    headers["Accept"] = "application/vnd.github.raw+json"
    response = requests.get(
        f"{_api_base(base_url)}/repos/{project}/contents/{file_path}",
        headers=headers,
        params={"ref": ref},
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def build_github_index(base_url: str, token: str, project: str, ref: str = "main"):
    file_paths = list_repo_files(base_url, token, project, ref)
    print(f"GitHub: found {len(file_paths)} source files in {project}@{ref}")

    documents = []
    for file_path in file_paths:
        try:
            content = fetch_file(base_url, token, project, ref, file_path)
        except requests.RequestException as e:
            print(f"GitHub: skipping {file_path}: {e}")
            continue
        if content.strip():
            documents.append((content, {"file_path": file_path, "repo": project, "ref": ref}))

    return build_index_from_documents(documents)
