import urllib.parse

import requests

from indexer import INDEXED_EXTENSIONS, build_index_from_documents

# Read-only: only GET requests are ever made against the GitLab API.


def _api(base_url: str, token: str, path: str, params: dict | None = None):
    response = requests.get(
        f"{base_url.rstrip('/')}/api/v4{path}",
        headers={"PRIVATE-TOKEN": token} if token else {},
        params=params or {},
        timeout=30,
    )
    response.raise_for_status()
    return response


def list_repo_files(base_url: str, token: str, project: str, ref: str) -> list[str]:
    project_id = urllib.parse.quote(project.strip().strip("/"), safe="")
    files = []
    page = 1
    while True:
        response = _api(
            base_url,
            token,
            f"/projects/{project_id}/repository/tree",
            {"recursive": "true", "per_page": 100, "page": page, "ref": ref},
        )
        for item in response.json():
            if item["type"] == "blob" and item["path"].endswith(INDEXED_EXTENSIONS):
                files.append(item["path"])
        next_page = response.headers.get("x-next-page")
        if not next_page:
            break
        page = int(next_page)
    return files


def fetch_file(base_url: str, token: str, project: str, ref: str, file_path: str) -> str:
    project_id = urllib.parse.quote(project.strip().strip("/"), safe="")
    encoded_path = urllib.parse.quote(file_path, safe="")
    response = _api(
        base_url,
        token,
        f"/projects/{project_id}/repository/files/{encoded_path}/raw",
        {"ref": ref},
    )
    return response.text


def build_gitlab_index(base_url: str, token: str, project: str, ref: str = "main"):
    file_paths = list_repo_files(base_url, token, project, ref)
    print(f"GitLab: found {len(file_paths)} source files in {project}@{ref}")

    documents = []
    for file_path in file_paths:
        try:
            content = fetch_file(base_url, token, project, ref, file_path)
        except requests.RequestException as e:
            print(f"GitLab: skipping {file_path}: {e}")
            continue
        if content.strip():
            documents.append((content, {"file_path": file_path, "repo": project, "ref": ref}))

    return build_index_from_documents(documents)
