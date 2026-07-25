"""Smoke tests for observability helpers (no OTEL exporter required)."""

from __future__ import annotations

import json
import logging

from common.observability.domain_flow import (
    domain_for_activity,
    domain_for_step,
    emit_step_log,
)
from common.observability.logging_setup import (
    JsonFormatter,
    TraceContextFilter,
    bind_tracking_id,
    tracking_id_var,
)
from common.observability.tracing import (
    current_trace_ids,
    temporal_interceptors,
    temporal_worker_interceptors,
)
from stores.ledger import InMemoryWorkflowLedger


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


def test_json_formatter_includes_domain_flow():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="step done",
        args=(),
        exc_info=None,
    )
    record.domain = "testing"  # type: ignore[attr-defined]
    record.flow = "testing.build_test_matrix"  # type: ignore[attr-defined]
    record.phase = "build_test_matrix"  # type: ignore[attr-defined]
    record.event = "step.complete"  # type: ignore[attr-defined]
    record.workflow_id = "wf-1"  # type: ignore[attr-defined]
    TraceContextFilter().filter(record)
    out = json.loads(JsonFormatter().format(record))
    assert out["domain"] == "testing"
    assert out["flow"] == "testing.build_test_matrix"
    assert out["phase"] == "build_test_matrix"
    assert out["event"] == "step.complete"
    assert out["workflow_id"] == "wf-1"


def test_domain_for_step_and_activity():
    assert domain_for_step("classify") == "intake"
    assert domain_for_step("build_test_matrix") == "testing"
    assert domain_for_step("publish_pdf") == "evidence"
    assert domain_for_step("release_hitl") == "governance"
    assert domain_for_activity("activity_execute_matrix") == "testing"
    assert domain_for_activity("activity_notify") == "notify"


def test_current_trace_ids_without_otel():
    tid, sid = current_trace_ids()
    assert isinstance(tid, str)
    assert isinstance(sid, str)


def test_temporal_interceptors_when_disabled(monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    assert temporal_interceptors() == []


def test_temporal_worker_interceptors_include_run_context(monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    interceptors = temporal_worker_interceptors()
    assert len(interceptors) >= 1
    assert interceptors[-1].__class__.__name__ == "RunContextInterceptor"


def test_upsert_step_emits_step_log(caplog):
    ledger = InMemoryWorkflowLedger()
    ledger.create_run(tracking_id="qa-log-1", workflow_id="wf-log-1")
    with caplog.at_level(logging.INFO, logger="qa.flow"):
        ledger.upsert_step("qa-log-1", "classify", {"route": "qa-route", "status": "ok"})
    assert any("step=classify" in r.getMessage() for r in caplog.records)
    assert any(getattr(r, "domain", None) == "intake" for r in caplog.records)
    assert any(getattr(r, "event", None) == "step.complete" for r in caplog.records)


def test_emit_step_log_direct(caplog):
    with caplog.at_level(logging.INFO, logger="qa.flow"):
        emit_step_log(
            tracking_id="qa-direct",
            step="notify",
            payload={"status": "sent"},
            workflow_id="wf-x",
        )
    assert any(getattr(r, "domain", None) == "notify" for r in caplog.records)
