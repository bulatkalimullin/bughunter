from __future__ import annotations

from prometheus_client import Counter, Histogram


class BHSMetrics:
    node_runs = Counter("bhs_node_runs_total", "Node executions", ["node"])
    run_duration = Histogram("bhs_run_duration_seconds", "End-to-end run duration")


BHS_METRICS = BHSMetrics()

__all__ = ["BHS_METRICS"]
