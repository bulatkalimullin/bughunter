from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path

from bhs.config import Settings
from bhs.graph import compile_swarm
from bhs.hypervisor.router import build_hypervisor_response
from bhs.observability.audit import set_audit_store
from bhs.observability.metrics import BHS_METRICS
from bhs.observability.otel import configure_otel
from bhs.observability.expose import start_metrics_server
from bhs.persistence.sqlite_store import SqliteRunStore
from bhs.sandbox.docker_runner import SandboxRunner
from bhs.storage.artifacts import build_artifact_store, retention_sweep_local


def main() -> None:
    parser = argparse.ArgumentParser(description="BugHunter Swarm CLI")
    parser.add_argument("--repo", type=Path, default=Path("."), help="Path to repository to analyze")
    parser.add_argument("--variants", nargs="*", default=[], help="Variant labels for AB branch")
    parser.add_argument("--metrics-port", type=int, default=0, help="Expose Prometheus metrics on port (0=off)")
    args = parser.parse_args()

    settings = Settings()
    configure_otel()
    if args.metrics_port > 0:
        start_metrics_server(args.metrics_port)

    store = SqliteRunStore(settings.sqlite_path)
    set_audit_store(store)

    artifacts = build_artifact_store(
        local_dir=settings.artifact_local_dir,
        minio_endpoint=settings.minio_endpoint,
        minio_access_key=settings.minio_access_key or "",
        minio_secret_key=settings.minio_secret_key or "",
        minio_bucket=settings.minio_bucket,
    )
    retention_sweep_local(settings.artifact_local_dir)

    run_id = str(uuid.uuid4())
    repo = args.repo.resolve()
    initial = {
        "run_id": run_id,
        "repo_path": str(repo),
        "repo_hash": "",
        "language": "",
        "framework": "",
        "config": {},
        "test_budget": 50,
        "sandbox_limits": {
            "cpu_seconds": 120.0,
            "memory_mb": 2048,
            "disk_mb": 1024,
            "pids_max": 128,
        },
        "iteration_count": 0,
        "max_iterations": 1,
        "variants": list(args.variants),
        "hypothesis_set": [],
        "node_statuses": {},
        "crash_or_leak": False,
        "multi_variant": len(args.variants) > 1,
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
    store.create_run(run_id, initial)

    if settings.redis_url:
        try:
            from bhs.persistence.redis_cache import RedisCache

            RedisCache(settings.redis_url).set_json(
                f"bhs:run:{run_id}:meta",
                {"repo": str(repo), "status": "started"},
                ttl_sec=7 * 86400,
            )
        except Exception:
            pass

    sandbox = SandboxRunner()
    report_dir = settings.artifact_local_dir / "reports"
    graph = compile_swarm(sandbox, artifacts, report_dir)

    t0 = time.perf_counter()
    final = graph.invoke(initial)
    dt = time.perf_counter() - t0
    BHS_METRICS.run_duration.observe(dt)

    store.save_state(run_id, dict(final), status=str(final.get("status", "success")))
    hv = final.get("last_hypervisor") or build_hypervisor_response(final).model_dump()  # type: ignore[arg-type]
    print(json.dumps(hv, indent=2, default=str))


if __name__ == "__main__":
    main()
