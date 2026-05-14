from __future__ import annotations

import os
from pathlib import Path

import pytest

from bhs.buglogger.bounty import bounty_usd
from bhs.buglogger.dedup import dedupe_bugs
from bhs.graph import compile_swarm
from bhs.sandbox.docker_runner import SandboxRunner
from bhs.state import BugSchema, BugType, Impact, Reproducibility, Severity
from bhs.storage.artifacts import LocalArtifactStore


def test_bounty_formula() -> None:
    bug = BugSchema(
        id="x",
        type=BugType.SECURITY,
        severity=Severity.HIGH,
        cvss_score=7.5,
        reproducibility=Reproducibility.ALWAYS,
        impact=Impact.CRASH,
    )
    assert bounty_usd(bug) == pytest.approx(50.0 * 1.0 * 1.3)


def test_dedupe_bugs() -> None:
    a = BugSchema(
        id="1",
        type=BugType.LOGIC,
        severity=Severity.LOW,
        cvss_score=3.0,
        reproducibility=Reproducibility.OFTEN,
        impact=Impact.SLOWDOWN,
        code_location="f.py:1",
        root_cause="dup",
    )
    b = BugSchema(
        id="2",
        type=BugType.LOGIC,
        severity=Severity.MEDIUM,
        cvss_score=6.0,
        reproducibility=Reproducibility.OFTEN,
        impact=Impact.SLOWDOWN,
        code_location="f.py:1",
        root_cause="dup",
    )
    out = dedupe_bugs([a, b])
    assert len(out) == 1
    assert out[0].severity == Severity.MEDIUM


def test_graph_smoke_local(tmp_path: Path) -> None:
    os.environ["BHS_SANDBOX_MODE"] = "local"
    (tmp_path / "ok.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    art = LocalArtifactStore(tmp_path / "art")
    g = compile_swarm(SandboxRunner(), art, tmp_path / "reports")
    run_id = "test-run"
    initial = {
        "run_id": run_id,
        "repo_path": str(tmp_path),
        "repo_hash": "",
        "language": "python",
        "framework": "",
        "config": {},
        "test_budget": 5,
        "sandbox_limits": {"cpu_seconds": 60.0, "memory_mb": 512, "disk_mb": 256, "pids_max": 64},
        "iteration_count": 0,
        "max_iterations": 1,
        "variants": [],
        "hypothesis_set": [],
        "node_statuses": {},
        "crash_or_leak": False,
        "multi_variant": False,
        "phase": "init",
        "status": "running",
        "next_action": "spawn_agent",
        "last_hypervisor": {},
        "reduced_scope": False,
        "artifacts": [],
        "bugs_found": [],
        "metrics": {},
        "runtime_logs": "",
        "coverage_pct": 0.0,
        "ab_metrics": {},
        "ab_metric_samples": {},
    }
    final = g.invoke(initial)
    assert final.get("phase") == "logging"
    hv = final.get("last_hypervisor")
    assert hv is not None
    data = hv if isinstance(hv, dict) else hv.model_dump() if hasattr(hv, "model_dump") else {}
    assert data.get("status") == "success"
    report = Path(tmp_path / "reports" / run_id / "BugHunter_Report.md")
    assert report.is_file()
