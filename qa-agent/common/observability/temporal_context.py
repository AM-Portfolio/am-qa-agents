"""Temporal interceptor — bind tracking_id ContextVar for activity/workflow logs."""

from __future__ import annotations

from typing import Any

from temporalio.worker import (
    ActivityInboundInterceptor,
    ExecuteActivityInput,
    Interceptor,
    WorkflowInboundInterceptor,
    WorkflowInterceptorClassInput,
)

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


class _ActivityRunContext(ActivityInboundInterceptor):
    async def execute_activity(self, input: ExecuteActivityInput) -> Any:
        tid = _tracking_from_args(tuple(input.args))
        name = getattr(input.fn, "__name__", "activity")
        with tracking_context(tid):
            if tid:
                set_span_tracking_id(tid)
            LOG.info(
                "activity.start",
                extra={"activity": name, "event": "activity.start"},
            )
            try:
                result = await self.next.execute_activity(input)
            except Exception:
                LOG.exception(
                    "activity.error",
                    extra={"activity": name, "event": "activity.error"},
                )
                raise
            LOG.info(
                "activity.complete",
                extra={"activity": name, "event": "activity.complete"},
            )
            return result


class RunContextInterceptor(Interceptor):
    """Attach tracking_id to activity ContextVars for structured logs."""

    def intercept_activity(
        self, next: ActivityInboundInterceptor
    ) -> ActivityInboundInterceptor:
        return _ActivityRunContext(next)

    def workflow_interceptor_class(
        self, input: WorkflowInterceptorClassInput
    ) -> type[WorkflowInboundInterceptor] | None:
        return None
