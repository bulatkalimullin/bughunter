from __future__ import annotations

import os
from pathlib import Path

import pytest

from bhs.buglogger.bounty import bounty_usd
from bhs.buglogger.dedup import dedupe_bugs
from bhs.config import Settings
from bhs.graph import compile_swarm
from bhs.nodes.pipeline import bug_logger_node
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
    g = compile_swarm(SandboxRunner(), art, tmp_path / "reports", Settings())
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


def test_feedback_loop_two_iterations(tmp_path: Path) -> None:
    os.environ["BHS_SANDBOX_MODE"] = "local"
    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")
    art = LocalArtifactStore(tmp_path / "art2")
    settings = Settings(max_iterations=2)
    g = compile_swarm(SandboxRunner(), art, tmp_path / "reports2", settings)
    run_id = "loop-run"
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
        "max_iterations": 2,
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
    assert int(final.get("iteration_count", -1)) == 1
    assert str(final.get("next_action")) == "finalize"


def test_feedback_loop_five_iterations(tmp_path: Path) -> None:
    os.environ["BHS_SANDBOX_MODE"] = "local"
    (tmp_path / "ok.py").write_text("y = 2\n", encoding="utf-8")
    art = LocalArtifactStore(tmp_path / "art5")
    settings = Settings(max_iterations=5, stop_bug_count=0)
    g = compile_swarm(SandboxRunner(), art, tmp_path / "reports5", settings)
    run_id = "loop-5"
    initial = {
        "run_id": run_id,
        "repo_path": str(tmp_path),
        "repo_hash": "",
        "language": "python",
        "framework": "",
        "config": {},
        "test_budget": 5,
        "sandbox_limits": {"cpu_seconds": 120.0, "memory_mb": 512, "disk_mb": 256, "pids_max": 64},
        "iteration_count": 0,
        "max_iterations": 5,
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
    assert int(final.get("iteration_count", -1)) == 4
    assert int((final.get("metrics") or {}).get("tests_run", 0)) == 5


def test_bug_logger_early_stop_by_deduped_count(tmp_path: Path) -> None:
    settings = Settings(stop_bug_count=2, max_iterations=100)
    raw = [
        {
            "id": "a",
            "type": "logic",
            "severity": "low",
            "cvss_score": 3.0,
            "reproducibility": "often",
            "impact": "slowdown",
            "code_location": "a.py:1",
            "root_cause": "issue a",
        },
        {
            "id": "b",
            "type": "logic",
            "severity": "low",
            "cvss_score": 3.0,
            "reproducibility": "often",
            "impact": "slowdown",
            "code_location": "b.py:2",
            "root_cause": "issue b",
        },
    ]
    state: dict = {
        "run_id": "early",
        "repo_path": str(tmp_path),
        "repo_hash": "abc",
        "bugs_found": raw,
        "iteration_count": 0,
        "max_iterations": 100,
        "artifacts": [],
        "node_statuses": {},
        "phase": "runtime",
        "status": "running",
        "next_action": "spawn_agent",
    }
    out = bug_logger_node(state, tmp_path / "rep_early", settings)
    assert out["next_action"] == "finalize"
    assert len(out["bugs_found"]) >= 2


def test_resolved_sandbox_cpu_seconds() -> None:
    s = Settings(max_iterations=250)
    assert s.resolved_sandbox_cpu_seconds() == pytest.approx(750.0)
    s2 = Settings(max_iterations=250, sandbox_cpu_budget_seconds=2000.0)
    assert s2.resolved_sandbox_cpu_seconds() == pytest.approx(2000.0)


def test_ollama_generate_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    import bhs.llm.ollama as ollama_mod

    class FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"message": {"content": "def test_from_llm():\n    assert True\n"}}

    class FakeClient:
        def __init__(self, *a: object, **kw: object) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *a: object) -> None:
            return None

        def post(self, url: str, json: dict | None = None) -> FakeResp:
            return FakeResp()

    monkeypatch.setattr(ollama_mod.httpx, "Client", FakeClient)
    s = Settings(ollama_enabled=True, ollama_model="gemma3:1b")
    body = ollama_mod.generate_pytest_module(
        s,
        language="python",
        hypothesis_set=["h1"],
        findings_summary="none",
    )
    assert body is not None
    assert "def test_from_llm" in body
