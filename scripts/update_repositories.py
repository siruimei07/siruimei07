"""Refresh the profile's public repository list using only GitHub's public endpoint."""

import json
import os
import re
import urllib.request
from pathlib import Path


def public_json(url):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "github-profile"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def escape_cell(value):
    value = " ".join((value or "").split())
    return re.sub(r"([\\`*_{}\[\]<>|])", r"\\\1", value)


def main():
    owner = os.environ.get("PROFILE_OWNER", "siruimei07")
    if not re.fullmatch(r"[A-Za-z0-9-]+", owner):
        raise ValueError("Invalid GitHub account name")
    repositories = []
    page = 1
    while True:
        # /users/{owner}/repos lists public repositories only. An optional workflow
        # token increases the rate limit; it does not change the endpoint's scope.
        batch = public_json(
            f"https://api.github.com/users/{owner}/repos?type=owner&per_page=100&page={page}"
        )
        if not isinstance(batch, list):
            raise ValueError("Unexpected GitHub API response")
        repositories.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    repositories = sorted(
        (
            repo for repo in repositories
            if not repo.get("private")
            and repo["owner"]["login"].lower() == owner.lower()
            and repo["name"].lower() != owner.lower()
        ),
        key=lambda repo: (repo.get("pushed_at") or "", repo["name"].lower()),
        reverse=True,
    )
    lines = ["| Repository | Description | Language |", "| :--- | :--- | :--- |"]
    for repo in repositories:
        language = repo.get("language")
        if not language:
            languages = public_json(
                f"https://api.github.com/repos/{owner}/{repo['name']}/languages"
            )
            if languages:
                language = max(languages, key=languages.get)
        flags = []
        if repo.get("fork"):
            flags.append("fork")
        if repo.get("archived"):
            flags.append("archived")
        suffix = f" · {' · '.join(flags)}" if flags else ""
        lines.append(
            f"| [{escape_cell(repo['name'])}]({repo['html_url']}){suffix} "
            f"| {escape_cell(repo.get('description')) or '—'} "
            f"| {escape_cell(language) or '—'} |"
        )

    readme = Path(__file__).resolve().parents[1] / "README.md"
    content = readme.read_text(encoding="utf-8")
    start, end = "<!-- PUBLIC-REPOS:START -->", "<!-- PUBLIC-REPOS:END -->"
    if content.count(start) != 1 or content.count(end) != 1:
        raise ValueError("Expected exactly one public repository section")
    before, rest = content.split(start)
    _, after = rest.split(end)
    updated = before + start + "\n" + "\n".join(lines) + "\n" + end + after
    readme.write_text(updated, encoding="utf-8", newline="\n")
    print(f"Updated public repository list: {len(repositories)} repositories")


if __name__ == "__main__":
    main()
