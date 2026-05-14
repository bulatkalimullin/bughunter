from __future__ import annotations

import uuid
from typing import Any

from bhs.buglogger.bounty import bounty_usd
from bhs.buglogger.dedup import bug_fingerprint, dedupe_bugs
from bhs.buglogger.export import export_bug_report_md
from bhs.buglogger.integrations import write_issue_drafts
from bhs.state import BugSchema, BugType, Impact, Reproducibility, Severity


def _cvss_from_severity(severity: Severity) -> float:
    return {
        Severity.CRITICAL: 9.5,
        Severity.HIGH: 7.5,
        Severity.MEDIUM: 5.5,
        Severity.LOW: 3.5,
        Severity.INFO: 0.0,
    }[severity]


def raw_findings_to_bugs(raw: list[dict[str, Any]]) -> list[BugSchema]:
    out: list[BugSchema] = []
    for r in raw:
        sev = Severity(str(r.get("severity", "medium")))
        bug = BugSchema(
            id=str(r.get("id") or uuid.uuid4()),
            type=BugType(str(r.get("type", "logic"))),
            severity=sev,
            cvss_score=float(r.get("cvss_score", _cvss_from_severity(sev))),
            reproducibility=Reproducibility(str(r.get("reproducibility", "often"))),
            impact=Impact(str(r.get("impact", "slowdown"))),
            code_location=str(r.get("code_location", "")),
            root_cause=str(r.get("root_cause", "")),
            test_repro=str(r.get("test_repro", "")),
            patch_suggestion=str(r.get("patch_suggestion", "")),
        )
        complexity = bool(r.get("complexity_bonus", False))
        bug.bounty_usd = bounty_usd(bug, complexity_bonus=complexity)
        bug.fingerprint = bug_fingerprint(bug)
        out.append(bug)
    return dedupe_bugs(out)


def finalize_report(
    *,
    run_id: str,
    repo_hash: str,
    raw_bugs: list[dict[str, Any]],
    report_dir: Any,
) -> dict[str, Any]:
    bugs = raw_findings_to_bugs(raw_bugs)
    report_path = report_dir / "BugHunter_Report.md"
    export_bug_report_md(bugs, report_path, repo_hash=repo_hash)
    drafts = write_issue_drafts(report_dir / "github_drafts", bugs, repo_hash)
    return {"bugs": [b.model_dump() for b in bugs], "report_path": str(report_path), "drafts": drafts}
