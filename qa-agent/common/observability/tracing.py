"""OpenTelemetry setup — mirrors support-agent / Plane A (OTLP HTTP + Temporal)."""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import FastAPI

LOG = logging.getLogger(__name__)
_FALSE = {"0", "false", "no", "off"}
_provider: Any = None
_instrumented: set[str] = set()

SERVICE_NAME_DEFAULT = "am-qa-agents"


def tracing_enabled() -> bool:
    if os.getenv("OTEL_SDK_DISABLED", "").strip().lower() in {"1", "true", "yes"}:
        return False
    if os.getenv("QA_AGENT_TRACING_ENABLED", "true").strip().lower() in _FALSE:
        return False
    return bool(_trace_endpoint())


def configure_tracing(*, service_name: str = SERVICE_NAME_DEFAULT) -> bool:
    """Configure shared TracerProvider for gateway and Temporal worker."""
    global _provider
    if not tracing_enabled():
        LOG.info("qa-agent tracing disabled")
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
    except ImportError:
        LOG.warning("OpenTelemetry deps missing — tracing disabled")
        return False

    if _provider is None:
        sample = _sample_probability()
        resource = Resource.create(
            {
                "service.name": service_name,
                "service.namespace": os.getenv("OTEL_SERVICE_NAMESPACE", "am-qa-agents"),
                "service.version": os.getenv("QA_AGENT_VERSION", "0.2.1"),
                "deployment.environment.name": os.getenv(
                    "APP_ENV", os.getenv("QA_AGENT_ENV", "unknown")
                ),
                "application": service_name,
            }
        )
        _provider = TracerProvider(
            resource=resource,
            sampler=ParentBased(TraceIdRatioBased(sample)),
        )
        _provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=_trace_endpoint()))
        )
        trace.set_tracer_provider(_provider)
        LOG.info(
            "OTEL tracing enabled service=%s sample=%s endpoint=%s",
            service_name,
            sample,
            _trace_endpoint(),
        )

    _instrument_dependencies()
    return True


def setup_tracing(app: FastAPI, *, service_name: str = SERVICE_NAME_DEFAULT) -> bool:
    """Instrument the live FastAPI app (must be composition.app, not a discarded sub-app)."""
    if not configure_tracing(service_name=service_name):
        return False
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    except ImportError:
        LOG.warning("FastAPI OTEL instrumentation unavailable")
        return False

    if not getattr(app.state, "qa_agent_tracing_instrumented", False):
        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls=(
                "metrics,health,ready,unified/health,router/health,"
                "health/live,health/ready,api/v1/health,api/platform/health"
            ),
        )
        app.state.qa_agent_tracing_instrumented = True
    return True


def temporal_interceptors() -> list[Any]:
    """Client-side Temporal interceptors (TracingInterceptor — inherited by Worker)."""
    if not tracing_enabled():
        return []
    try:
        from temporalio.contrib.opentelemetry import TracingInterceptor

        return [TracingInterceptor()]
    except ImportError:
        LOG.warning("Temporal OTEL interceptor unavailable")
        return []


def temporal_worker_interceptors() -> list[Any]:
    """Worker-only interceptors (tracking_id ContextVar for structured logs)."""
    try:
        from common.observability.temporal_context import RunContextInterceptor

        return [RunContextInterceptor()]
    except ImportError:
        LOG.warning("RunContextInterceptor unavailable")
        return []


def current_trace_ids() -> tuple[str, str]:
    """Return (trace_id, span_id) hex from the active OTEL span, or empty strings."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context() if span else None
        if not ctx or not ctx.is_valid:
            return "", ""
        return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")
    except Exception:  # noqa: BLE001
        return "", ""


def set_span_tracking_id(tracking_id: str) -> None:
    if not tracking_id:
        return
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span and span.is_recording():
            span.set_attribute("qa.tracking_id", tracking_id)
            span.set_attribute("correlation.id", tracking_id)
    except Exception:  # noqa: BLE001
        return


def _instrument_dependencies() -> None:
    instrumentors = (
        ("httpx", "opentelemetry.instrumentation.httpx", "HTTPXClientInstrumentor"),
    )
    for name, module_name, class_name in instrumentors:
        if name in _instrumented:
            continue
        try:
            module = __import__(module_name, fromlist=[class_name])
            getattr(module, class_name)().instrument()
        except ImportError:
            LOG.info("%s OTEL instrumentation unavailable", name)
            continue
        except Exception:  # noqa: BLE001
            LOG.exception("failed to enable %s OTEL instrumentation", name)
            continue
        _instrumented.add(name)
        LOG.info("%s OTEL instrumentation enabled", name)


def _trace_endpoint() -> str:
    traces = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
    if traces:
        return traces
    base = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    return f"{base.rstrip('/')}/v1/traces" if base else ""


def _sample_probability() -> float:
    raw = os.getenv(
        "OTEL_TRACES_SAMPLER_ARG",
        os.getenv("TRACING_SAMPLING_PROBABILITY", "1.0"),
    )
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        return 1.0
