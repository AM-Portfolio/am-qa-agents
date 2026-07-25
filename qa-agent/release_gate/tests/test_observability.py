"""Smoke tests for observability helpers (no OTEL exporter required)."""

from __future__ import annotations

import json
import logging

from common.observability.logging_setup import (
    JsonFormatter,
    TraceContextFilter,
    bind_tracking_id,
    tracking_id_var,
)
from common.observability.tracing import current_trace_ids, temporal_interceptors


def test_tracking_id_contextvar():
    bind_tracking_id("qa-abc123")
    assert tracking_id_var.get() == "qa-abc123"
    bind_tracking_id("")
    assert tracking_id_var.get() == ""


def test_json_formatter_includes_ids():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    TraceContextFilter().filter(record)
    bind_tracking_id("qa-xyz")
    TraceContextFilter().filter(record)
    out = json.loads(JsonFormatter().format(record))
    assert out["service"]
    assert out["message"] == "hello"
    assert out["tracking_id"] == "qa-xyz"
    assert "trace_id" in out
    assert "span_id" in out


def test_current_trace_ids_without_otel():
    tid, sid = current_trace_ids()
    assert isinstance(tid, str)
    assert isinstance(sid, str)


def test_temporal_interceptors_when_disabled(monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    assert temporal_interceptors() == []
