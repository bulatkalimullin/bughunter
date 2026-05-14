from __future__ import annotations

import operator
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class BugType(str, Enum):
    RUNTIME = "runtime"
    MEMORY = "memory"
    LOGIC = "logic"
    SECURITY = "security"
    PERFORMANCE = "performance"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Reproducibility(str, Enum):
    ALWAYS = "always"
    OFTEN = "often"
    RARE = "rare"
    ONE_OFF = "one-off"


class Impact(str, Enum):
    DATA_LOSS = "data_loss"
    CRASH = "crash"
    LEAK = "leak"
    SLOWDOWN = "slowdown"
    PRIVILEGE_ESCALATION = "privilege_escalation"


class BugSchema(BaseModel):
    """Structured bug record (plan §4)."""

    id: str
    type: BugType
    severity: Severity
    cvss_score: float = Field(ge=0.0, le=10.0)
    reproducibility: Reproducibility
    impact: Impact
    code_location: str = ""
    root_cause: str = ""
    test_repro: str = ""
    patch_suggestion: str = ""
    bounty_usd: float = 0.0
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    fingerprint: str = ""


class SandboxLimits(BaseModel):
    cpu_seconds: float = 300.0
    memory_mb: int = 4096
    disk_mb: int = 2048
    pids_max: int = 256
    cpu_cores: float | None = None


class NodeStatus(BaseModel):
    node_id: str
    status: Literal["pending", "running", "success", "failed", "skipped"] = "pending"
    attempts: int = 0
    last_error: str | None = None


class HypervisorResponse(BaseModel):
    """JSON contract for orchestrator output (plan §4)."""

    phase: Literal["static", "test", "runtime", "memory", "ab_test", "logging", "init", "done"]
    status: Literal["running", "success", "failed", "partial"]
    artifacts: list[str] = Field(default_factory=list)
    bugs_found: list[BugSchema] = Field(default_factory=list)
    next_action: Literal["spawn_agent", "retry", "finalize", "abort"]
    metrics: dict[str, Any] = Field(default_factory=dict)


def _merge_dicts(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    out = dict(a)
    out.update(b)
    return out


class BHSState(TypedDict, total=False):
    """LangGraph shared state."""

    repo_hash: str
    language: str
    framework: str
    config: dict[str, Any]
    test_budget: int
    sandbox_limits: dict[str, Any]
    iteration_count: int
    max_iterations: int
    repo_path: str
    run_id: str
    variants: list[str]
    hypothesis_set: list[str]
    node_statuses: dict[str, dict[str, Any]]
    crash_or_leak: bool
    multi_variant: bool
    phase: str
    status: str
    next_action: str
    last_hypervisor: dict[str, Any]
    reduced_scope: bool
    artifacts: Annotated[list[str], operator.add]
    # Serialized bugs (LangGraph checkpoint-friendly)
    bugs_found: Annotated[list[dict[str, Any]], operator.add]
    metrics: dict[str, Any]
    runtime_logs: str
    coverage_pct: float
    ab_metrics: dict[str, Any]
    ab_metric_samples: dict[str, list[float]]
