"""HTTP middleware — request logs + X-Trace-Id / X-Correlation-Id headers."""

from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from common.observability.logging_setup import get_logger, tracking_context
from common.observability.tracing import current_trace_ids, set_span_tracking_id

LOG = get_logger("qa.http")

_SKIP = {
    "/metrics",
    "/health",
    "/ready",
    "/unified/health",
    "/api/platform/health",
}


class TraceLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Prefer inbound correlation / tracking headers
        corr = (
            request.headers.get("x-correlation-id")
            or request.headers.get("x-tracking-id")
            or ""
        ).strip()
        if not corr and path.startswith("/v2/"):
            corr = f"req-{uuid.uuid4().hex[:12]}"

        with tracking_context(corr):
            if corr:
                set_span_tracking_id(corr)
            start = time.perf_counter()
            if path not in _SKIP:
                LOG.info(
                    "request.start method=%s path=%s",
                    request.method,
                    path,
                    extra={"event": "request.start"},
                )
            response = await call_next(request)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            tid, sid = current_trace_ids()
            if tid:
                response.headers["X-Trace-Id"] = tid
            if sid:
                response.headers["X-Span-Id"] = sid
            if corr:
                response.headers["X-Correlation-Id"] = corr
            if path not in _SKIP:
                LOG.info(
                    "request.end method=%s path=%s status=%s duration_ms=%s",
                    request.method,
                    path,
                    response.status_code,
                    elapsed_ms,
                    extra={"event": "request.end"},
                )
            return response


def install_http_tracing(app: FastAPI) -> None:
    app.add_middleware(TraceLoggingMiddleware)
