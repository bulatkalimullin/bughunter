from __future__ import annotations

from pathlib import Path

from bhs.state import BugSchema


def export_bug_report_md(bugs: list[BugSchema], out: Path, repo_hash: str = "") -> None:
    lines = [
        "# BugHunter Swarm Report",
        "",
        f"repo_hash: `{repo_hash}`",
        "",
        "| id | type | severity | CVSS | bounty | location |",
        "|----|------|----------|------|--------|----------|",
    ]
    for b in bugs:
        lines.append(
            f"| {b.id[:8]}… | {b.type.value} | {b.severity.value} | {b.cvss_score} | {b.bounty_usd} | {b.code_location} |"
        )
    lines.append("")
    for b in bugs:
        lines.extend(
            [
                f"## {b.id}",
                f"- **root_cause**: {b.root_cause}",
                f"- **repro**: ```\n{b.test_repro}\n```",
                f"- **patch_suggestion**:\n```diff\n{b.patch_suggestion}\n```",
                "",
            ]
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
