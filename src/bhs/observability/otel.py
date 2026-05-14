from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import NoOpTracerProvider

_tracer_provider: TracerProvider | None = None


def configure_otel(service_name: str = "bughunter-swarm") -> None:
    global _tracer_provider
    bhs_ep = os.environ.get("BHS_OTEL_EXPORTER_OTLP_ENDPOINT")
    if bhs_ep:
        os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", bhs_ep)
    if not (
        os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        or os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    ):
        trace.set_tracer_provider(NoOpTracerProvider())
        return
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    except Exception:  # pragma: no cover
        trace.set_tracer_provider(NoOpTracerProvider())
        return

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _tracer_provider = provider


def get_tracer(name: str = "bhs"):
    return trace.get_tracer(name)
