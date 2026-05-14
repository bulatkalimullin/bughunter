"""HyperVisor: quotas, retry policy, routing hints."""

from __future__ import annotations

import hashlib
from typing import Any

from bhs.state import BHSState, HypervisorResponse, SandboxLimits


class QuotaExceeded(Exception):
    pass


def _limits(state: BHSState) -> SandboxLimits:
    raw = state.get("sandbox_limits") or {}
    return SandboxLimits.model_validate(raw)


def check_quotas(state: BHSState) -> None:
    lim = _limits(state)
    m = state.get("metrics") or {}
    cpu = float(m.get("cpu_sec", 0.0))
    mem = float(m.get("mem_mb", 0.0))
    if cpu > lim.cpu_seconds:
        raise QuotaExceeded(f"CPU budget exceeded: {cpu}s > {lim.cpu_seconds}s")
    if mem > lim.memory_mb:
        raise QuotaExceeded(f"Memory budget exceeded: {mem}MB > {lim.memory_mb}MB")


def should_retry_node(node_id: str, state: BHSState, max_attempts: int = 3) -> bool:
    statuses = state.get("node_statuses") or {}
    info = statuses.get(node_id) or {}
    attempts = int(info.get("attempts", 0))
    status = str(info.get("status", "pending"))
    if status == "failed" and attempts < max_attempts:
        return True
    return False


def next_after_failure(state: BHSState) -> str:
    if should_retry_node("runtime_executor", state):
        return "retry"
    return "finalize"


def reduce_scope(state: BHSState) -> dict[str, Any]:
    lim = _limits(state)
    return {
        "sandbox_limits": {
            "cpu_seconds": max(30.0, lim.cpu_seconds * 0.5),
            "memory_mb": max(512, lim.memory_mb // 2),
            "disk_mb": max(256, lim.disk_mb // 2),
            "pids_max": max(32, lim.pids_max // 2),
            **(
                {"cpu_cores": max(0.25, (lim.cpu_cores or 1.0) * 0.5)}
                if lim.cpu_cores is not None
                else {}
            ),
        },
        "reduced_scope": True,
        "test_budget": max(1, (state.get("test_budget") or 10) // 2),
    }


def repo_hash_from_path(repo_path: str) -> str:
    h = hashlib.sha256()
    h.update(repo_path.encode())
    return h.hexdigest()[:12]


def build_hypervisor_response(state: BHSState) -> HypervisorResponse:
    bugs_raw = state.get("bugs_found") or []
    from bhs.state import BugSchema

    bugs = []
    for b in bugs_raw:
        if isinstance(b, dict):
            bugs.append(BugSchema.model_validate(b))
        else:
            bugs.append(b)

    phase = str(state.get("phase") or "init")
    st = str(state.get("status") or "running")
    next_action = str(state.get("next_action") or "spawn_agent")
    artifacts = list(state.get("artifacts") or [])
    metrics = dict(state.get("metrics") or {})
    if "coverage_pct" in state:
        metrics.setdefault("coverage_pct", float(state["coverage_pct"] or 0.0))

    return HypervisorResponse(
        phase=phase,  # type: ignore[arg-type]
        status=st,  # type: ignore[arg-type]
        artifacts=artifacts,
        bugs_found=bugs,
        next_action=next_action,  # type: ignore[arg-type]
        metrics=metrics,
    )
