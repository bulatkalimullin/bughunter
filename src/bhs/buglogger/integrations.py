from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from bhs.state import BugSchema


def draft_github_issue_markdown(bug: BugSchema, repo_hash: str) -> str:
    return "\n".join(
        [
            f"## [BHS] {bug.type.value} / {bug.severity.value}",
            f"**CVSS**: {bug.cvss_score}  **Bounty (synthetic)**: ${bug.bounty_usd}",
            f"**Location**: `{bug.code_location}`",
            f"**Reproducibility**: {bug.reproducibility.value}",
            "",
            "### Root cause",
            bug.root_cause,
            "",
            "### Repro",
            "```",
            bug.test_repro,
            "```",
            "",
            "### Suggested patch",
            "```diff",
            bug.patch_suggestion,
            "```",
            "",
            f"_repo_hash: {repo_hash}_",
        ]
    )


def write_issue_drafts(dir_path: Path, bugs: list[BugSchema], repo_hash: str) -> list[str]:
    dir_path.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for b in bugs:
        p = dir_path / f"issue-{b.id}.md"
        p.write_text(draft_github_issue_markdown(b, repo_hash), encoding="utf-8")
        paths.append(str(p))
    return paths


def jira_payload(bug: BugSchema, project_key: str) -> dict[str, Any]:
    return {
        "fields": {
            "project": {"key": project_key},
            "summary": f"[BHS] {bug.type.value}: {bug.code_location or bug.root_cause[:80]}",
            "description": draft_github_issue_markdown(bug, ""),
            "issuetype": {"name": "Bug"},
        }
    }


def post_github_issue(
    token: str,
    owner_repo: str,
    title: str,
    body: str,
) -> dict[str, Any]:
    owner, repo = owner_repo.split("/", 1)
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    with httpx.Client(timeout=30.0) as client:
        r = client.post(url, headers=headers, json={"title": title, "body": body})
        r.raise_for_status()
        return r.json()
