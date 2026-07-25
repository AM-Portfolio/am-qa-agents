"""Temporal interceptor — bind tracking_id ContextVar + domain/workflow activity logs."""

from __future__ import annotations

import time
from typing import Any

from temporalio import activity
from temporalio.worker import (
    ActivityInboundInterceptor,
    ExecuteActivityInput,
    Interceptor,
    WorkflowInboundInterceptor,
    WorkflowInterceptorClassInput,
)

from common.observability.domain_flow import domain_for_activity
from common.observability.logging_setup import get_logger, tracking_context
from common.observability.tracing import set_span_tracking_id

LOG = get_logger("qa.activity")


def _tracking_from_args(args: tuple[Any, ...]) -> str:
    if not args:
        return ""
    first = args[0]
    if isinstance(first, dict):
        return str(first.get("tracking_id") or "")
    if isinstance(first, str) and first.startswith("qa-"):
        return first
    for arg in args[1:]:
        if isinstance(arg, dict) and arg.get("tracking_id"):
            return str(arg["tracking_id"])
    return ""


def _activity_meta(name: str) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "activity": name,
        "domain": domain_for_activity(name),
        "flow": f"{domain_for_activity(name)}.{name}",
    }
    try:
        info = activity.info()
        meta["workflow_id"] = info.workflow_id or ""
        meta["workflow_run_id"] = info.workflow_run_id or ""
        meta["activity_id"] = info.activity_id or ""
        meta["attempt"] = info.attempt
    except Exception:  # noqa: BLE001
        pass
    return meta


class _ActivityRunContext(ActivityInboundInterceptor):
    async def execute_activity(self, input: ExecuteActivityInput) -> Any:
        tid = _tracking_from_args(tuple(input.args))
        name = getattr(input.fn, "__name__", "activity")
        with tracking_context(tid):
            if tid:
                set_span_tracking_id(tid)
            base = _activity_meta(name)
            LOG.info(
                "activity.start name=%s domain=%s workflow_id=%s",
                name,
                base.get("domain"),
                base.get("workflow_id") or "-",
                extra={**base, "event": "activity.start"},
            )
            start = time.perf_counter()
            try:
                result = await self.next.execute_activity(input)
            except Exception:
                LOG.exception(
                    "activity.error name=%s domain=%s",
                    name,
                    base.get("domain"),
                    extra={**base, "event": "activity.error"},
                )
                raise
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            LOG.info(
                "activity.complete name=%s domain=%s duration_ms=%s",
                name,
                base.get("domain"),
                elapsed_ms,
                extra={**base, "event": "activity.complete", "duration_ms": elapsed_ms},
            )
            return result


class RunContextInterceptor(Interceptor):
    """Attach tracking_id + domain/workflow fields for structured activity logs."""

    def intercept_activity(
        self, next: ActivityInboundInterceptor
    ) -> ActivityInboundInterceptor:
        return _ActivityRunContext(next)

    def workflow_interceptor_class(
        self, input: WorkflowInterceptorClassInput
    ) -> type[WorkflowInboundInterceptor] | None:
        return None
