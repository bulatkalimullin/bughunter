from __future__ import annotations

import ast
import json
import time
import uuid
from pathlib import Path
from typing import Any

from scipy import stats

from bhs.hypervisor.router import build_hypervisor_response, repo_hash_from_path
from bhs.observability.audit import audit
from bhs.observability.metrics import BHS_METRICS
from bhs.observability.otel import get_tracer
from bhs.sandbox.docker_runner import SandboxRunner
from bhs.state import BHSState, BugType, Impact, Reproducibility, Severity
from bhs.storage.artifacts import ArtifactStore


def hypervisor_init(state: BHSState) -> dict[str, Any]:
    tracer = get_tracer()
    with tracer.start_as_current_span("hypervisor.init"):
        repo = state.get("repo_path") or "."
        rh = state.get("repo_hash") or repo_hash_from_path(str(Path(repo).resolve()))
        audit(state.get("run_id", ""), "hypervisor", state, "init", {"repo": repo})
        return {
            "repo_hash": rh,
            "phase": "init",
            "status": "running",
            "next_action": "spawn_agent",
            "iteration_count": int(state.get("iteration_count", 0)),
            "node_statuses": dict(state.get("node_statuses") or {}),
            "metrics": dict(state.get("metrics") or {}),
        }


def code_analyzer_node(state: BHSState) -> dict[str, Any]:
    tracer = get_tracer()
    with tracer.start_as_current_span("node.code_analyzer"):
        BHS_METRICS.node_runs.labels(node="code_analyzer").inc()
        repo = Path(state.get("repo_path", ".")).resolve()
        hyps: list[str] = []
        findings: list[dict[str, Any]] = []
        if (repo / "pyproject.toml").exists() or any(repo.glob("*.py")):
            state["language"] = state.get("language") or "python"
        for py in repo.rglob("*.py"):
            if ".venv" in py.parts or "node_modules" in py.parts:
                continue
            try:
                tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            except SyntaxError as e:
                findings.append(
                    {
                        "id": str(uuid.uuid4()),
                        "type": BugType.LOGIC.value,
                        "severity": Severity.MEDIUM.value,
                        "cvss_score": 5.0,
                        "reproducibility": Reproducibility.ALWAYS.value,
                        "impact": Impact.SLOWDOWN.value,
                        "code_location": f"{py}:{e.lineno or 0}",
                        "root_cause": f"SyntaxError: {e.msg}",
                        "test_repro": f"python -m py_compile {py}",
                        "patch_suggestion": "",
                    }
                )
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler) and node.type is None:
                    hyps.append(f"bare_except:{py}:{node.lineno}")
                    findings.append(
                        {
                            "id": str(uuid.uuid4()),
                            "type": BugType.LOGIC.value,
                            "severity": Severity.LOW.value,
                            "cvss_score": 3.5,
                            "reproducibility": Reproducibility.OFTEN.value,
                            "impact": Impact.SLOWDOWN.value,
                            "code_location": f"{py}:{node.lineno}",
                            "root_cause": "Bare except swallows BaseException including KeyboardInterrupt",
                            "test_repro": "pytest -q  # add test raising Exception inside guarded block",
                            "patch_suggestion": "- except:\n+ except Exception:",
                        }
                    )
        ns = dict(state.get("node_statuses") or {})
        ns["code_analyzer"] = {"status": "success", "attempts": ns.get("code_analyzer", {}).get("attempts", 0) + 1}
        audit(state.get("run_id", ""), "code_analyzer", state, "static_complete", {"findings": len(findings)})
        return {
            "phase": "static",
            "hypothesis_set": hyps,
            "bugs_found": findings,
            "node_statuses": ns,
            "next_action": "spawn_agent",
        }


def test_generator_node(state: BHSState) -> dict[str, Any]:
    tracer = get_tracer()
    with tracer.start_as_current_span("node.test_generator"):
        BHS_METRICS.node_runs.labels(node="test_generator").inc()
        repo = Path(state.get("repo_path", ".")).resolve()
        gen_dir = repo / ".bhs" / "generated"
        gen_dir.mkdir(parents=True, exist_ok=True)
        test_file = gen_dir / "test_bhs_smoke.py"
        test_file.write_text(
            "\n".join(
                [
                    "def test_smoke():",
                    "    assert True",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        ns = dict(state.get("node_statuses") or {})
        ns["test_generator"] = {"status": "success", "attempts": ns.get("test_generator", {}).get("attempts", 0) + 1}
        audit(state.get("run_id", ""), "test_generator", state, "tests_materialized", {"path": str(test_file)})
        return {
            "phase": "test",
            "artifacts": [str(test_file)],
            "node_statuses": ns,
            "next_action": "spawn_agent",
        }


def runtime_executor_node(state: BHSState, sandbox: SandboxRunner, artifacts: ArtifactStore) -> dict[str, Any]:
    tracer = get_tracer()
    with tracer.start_as_current_span("node.runtime_executor"):
        BHS_METRICS.node_runs.labels(node="runtime_executor").inc()
        repo = str(Path(state.get("repo_path", ".")).resolve())
        limits = dict(state.get("sandbox_limits") or {})
        t0 = time.perf_counter()
        cmd = ["python", "-m", "compileall", "-q", "."]
        res = sandbox.run_command(cmd, repo, limits, env={"PYTHONDONTWRITEBYTECODE": "1"})
        dt = time.perf_counter() - t0
        crash = res.exit_code != 0 or res.oom
        uri = artifacts.put_bytes(
            str(state.get("run_id", "local")),
            "runtime/compileall.log",
            (res.stdout + "\n" + res.stderr).encode(),
            "text/plain",
        )
        metrics = dict(state.get("metrics") or {})
        metrics["cpu_sec"] = float(metrics.get("cpu_sec", 0.0)) + dt
        metrics["mem_mb"] = float(metrics.get("mem_mb", 0.0)) + (4096.0 if res.oom else 0.0)
        metrics["tests_run"] = int(metrics.get("tests_run", 0)) + 1
        ns = dict(state.get("node_statuses") or {})
        ns["runtime_executor"] = {
            "status": "failed" if crash else "success",
            "attempts": ns.get("runtime_executor", {}).get("attempts", 0) + 1,
            "last_error": res.stderr[:2000] if crash else None,
        }
        new_bugs: list[dict[str, Any]] = []
        if crash:
            new_bugs.append(
                {
                    "id": str(uuid.uuid4()),
                    "type": BugType.RUNTIME.value,
                    "severity": Severity.HIGH.value,
                    "cvss_score": 7.0,
                    "reproducibility": Reproducibility.ALWAYS.value,
                    "impact": Impact.CRASH.value,
                    "code_location": repo,
                    "root_cause": "compileall failed inside sandbox",
                    "test_repro": " ".join(cmd),
                    "patch_suggestion": "",
                }
            )
        audit(state.get("run_id", ""), "runtime_executor", state, "runtime_complete", {"exit": res.exit_code})
        return {
            "phase": "runtime",
            "runtime_logs": res.stderr + res.stdout,
            "crash_or_leak": crash or res.oom or ("MemoryError" in res.stderr),
            "multi_variant": len(state.get("variants") or []) > 1,
            "artifacts": [uri],
            "bugs_found": new_bugs,
            "metrics": metrics,
            "node_statuses": ns,
            "coverage_pct": float(state.get("coverage_pct", 0.0)),
            "next_action": "spawn_agent",
        }


def memory_profiler_node(state: BHSState, artifacts: ArtifactStore) -> dict[str, Any]:
    tracer = get_tracer()
    with tracer.start_as_current_span("node.memory_profiler"):
        BHS_METRICS.node_runs.labels(node="memory_profiler").inc()
        logs = state.get("runtime_logs") or ""
        new_bugs: list[dict[str, Any]] = []
        if "MemoryError" in logs or "leak" in logs.lower():
            new_bugs.append(
                {
                    "id": str(uuid.uuid4()),
                    "type": BugType.MEMORY.value,
                    "severity": Severity.MEDIUM.value,
                    "cvss_score": 6.0,
                    "reproducibility": Reproducibility.OFTEN.value,
                    "impact": Impact.LEAK.value,
                    "code_location": str(state.get("repo_path", "")),
                    "root_cause": "Heuristic memory issue from runtime logs",
                    "test_repro": str(logs[:2000]),
                    "patch_suggestion": "",
                    "complexity_bonus": True,
                }
            )
        uri = artifacts.put_bytes(
            str(state.get("run_id", "local")),
            "memory/heuristic.md",
            logs.encode()[:200_000],
            "text/markdown",
        )
        ns = dict(state.get("node_statuses") or {})
        ns["memory_profiler"] = {"status": "success", "attempts": ns.get("memory_profiler", {}).get("attempts", 0) + 1}
        return {
            "phase": "memory",
            "artifacts": [uri],
            "bugs_found": new_bugs,
            "node_statuses": ns,
            "next_action": "spawn_agent",
        }


def ab_tester_node(state: BHSState, artifacts: ArtifactStore) -> dict[str, Any]:
    tracer = get_tracer()
    with tracer.start_as_current_span("node.ab_tester"):
        BHS_METRICS.node_runs.labels(node="ab_tester").inc()
        variants = list(state.get("variants") or [])
        metrics_lists: dict[str, list[float]] = state.get("ab_metric_samples") or {}  # type: ignore[assignment]
        if len(variants) >= 2 and len(metrics_lists) >= 2:
            keys = list(metrics_lists.keys())[:2]
            a = metrics_lists[keys[0]]
            b = metrics_lists[keys[1]]
            if len(a) > 2 and len(b) > 2:
                t = stats.ttest_ind(a, b, equal_var=False)
                pvalue = float(t.pvalue)
            else:
                pvalue = 1.0
        else:
            pvalue = 1.0
        report = {"pvalue": pvalue, "variants": variants}
        uri = artifacts.put_bytes(
            str(state.get("run_id", "local")),
            "ab/report.json",
            json.dumps(report).encode(),
            "application/json",
        )
        ns = dict(state.get("node_statuses") or {})
        ns["ab_tester"] = {"status": "success", "attempts": ns.get("ab_tester", {}).get("attempts", 0) + 1}
        return {
            "phase": "ab_test",
            "ab_metrics": report,
            "artifacts": [uri],
            "node_statuses": ns,
            "next_action": "spawn_agent",
        }


def bug_logger_node(state: BHSState, report_dir: Path) -> dict[str, Any]:
    tracer = get_tracer()
    with tracer.start_as_current_span("node.bug_logger"):
        BHS_METRICS.node_runs.labels(node="bug_logger").inc()
        from bhs.buglogger.service import finalize_report

        raw = list(state.get("bugs_found") or [])
        run_id = str(state.get("run_id", "local"))
        out = finalize_report(
            run_id=run_id,
            repo_hash=str(state.get("repo_hash", "")),
            raw_bugs=raw,
            report_dir=report_dir / run_id,
        )
        ns = dict(state.get("node_statuses") or {})
        ns["bug_logger"] = {"status": "success", "attempts": ns.get("bug_logger", {}).get("attempts", 0) + 1}
        merged_state = {
            **dict(state),
            "bugs_found": out["bugs"],
            "phase": "logging",
            "artifacts": [*list(state.get("artifacts") or []), out["report_path"]],
            "status": "success",
            "next_action": "finalize",
        }
        hv = build_hypervisor_response(merged_state)  # type: ignore[arg-type]
        audit(state.get("run_id", ""), "bug_logger", state, "report", {"path": out["report_path"]})
        return {
            "phase": "logging",
            "status": "success",
            "next_action": "finalize",
            "artifacts": [out["report_path"], *out["drafts"]],
            "node_statuses": ns,
            "last_hypervisor": hv.model_dump(),
        }


def route_post_runtime(state: BHSState) -> str:
    if state.get("crash_or_leak"):
        return "memory"
    if state.get("multi_variant"):
        return "ab"
    return "log"


def route_feedback(state: BHSState) -> str:
    it = int(state.get("iteration_count", 0))
    max_it = int(state.get("max_iterations", 1))
    if state.get("next_action") == "finalize" or it + 1 >= max_it:
        return "end"
    return "again"


def feedback_tick(state: BHSState) -> dict[str, Any]:
    return {"iteration_count": int(state.get("iteration_count", 0)) + 1}
