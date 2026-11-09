"""Temporal workflow: run a stepped API flow execution."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from orchestrator.activities.flow_execute import activity_flow_execute


@workflow.defn(name="FlowExecuteWorkflow")
class FlowExecuteWorkflow:
    @workflow.run
    async def run(self, args: dict[str, Any]) -> dict[str, Any]:
        return await workflow.execute_activity(
            activity_flow_execute,
            args,
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
