"""Optional Prometheus metrics HTTP endpoint."""

from __future__ import annotations

from typing import Any

from prometheus_client import start_http_server


def start_metrics_server(port: int = 9108) -> Any:
    return start_http_server(port)
