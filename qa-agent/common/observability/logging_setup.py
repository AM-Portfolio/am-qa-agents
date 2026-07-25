"""Structured JSON logs with service + OTEL trace_id/span_id + tracking_id (CLS-aligned)."""

from __future__ import annotations

import json
import logging
import os
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Iterator

SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME") or os.getenv("APP_NAME") or "am-qa-agents"

tracking_id_var: ContextVar[str] = ContextVar("qa_tracking_id", default="")


def bind_tracking_id(tracking_id: str | None) -> None:
    tracking_id_var.set(str(tracking_id or ""))


@contextmanager
def tracking_context(tracking_id: str | None) -> Iterator[None]:
    token = tracking_id_var.set(str(tracking_id or ""))
    try:
        yield
    finally:
        tracking_id_var.reset(token)


class TraceContextFilter(logging.Filter):
    """Inject service / trace_id / span_id / tracking_id onto every LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = SERVICE_NAME  # type: ignore[attr-defined]
        try:
            from common.observability.tracing import current_trace_ids

            tid, sid = current_trace_ids()
        except Exception:  # noqa: BLE001
            tid, sid = "", ""
        record.trace_id = tid  # type: ignore[attr-defined]
        record.span_id = sid  # type: ignore[attr-defined]
        record.tracking_id = tracking_id_var.get() or ""  # type: ignore[attr-defined]
        return True


class JsonFormatter(logging.Formatter):
    """am-logging CLS-shaped console JSON (snake_case fields)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service", SERVICE_NAME),
            "trace_id": getattr(record, "trace_id", "") or "",
            "span_id": getattr(record, "span_id", "") or "",
            "tracking_id": getattr(record, "tracking_id", "") or "",
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Optional extras commonly used in activities
        for key in ("activity", "workflow_id", "phase", "event"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, default=str)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        tid = getattr(record, "trace_id", "") or "-"
        sid = getattr(record, "span_id", "") or "-"
        track = getattr(record, "tracking_id", "") or "-"
        svc = getattr(record, "service", SERVICE_NAME)
        ts = self.formatTime(record, self.datefmt)
        return (
            f"[{ts}] | [{svc}] | [{tid}:{sid}] | [tracking={track}] | "
            f"{record.levelname} | {record.name} | {record.getMessage()}"
        )


def configure_logging(*, force: bool = False) -> None:
    """Configure root logger once for gateway + worker processes."""
    root = logging.getLogger()
    if root.handlers and not force:
        # Still ensure filter present on existing handlers
        filt = TraceContextFilter()
        for h in root.handlers:
            if not any(isinstance(f, TraceContextFilter) for f in h.filters):
                h.addFilter(filt)
        return

    level_name = (os.getenv("LOG_LEVEL") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    fmt_mode = (os.getenv("LOG_FORMAT") or "json").strip().lower()

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(TraceContextFilter())
    handler.setFormatter(JsonFormatter() if fmt_mode == "json" else TextFormatter())

    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
