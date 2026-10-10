"""CommitSptWorkflow — branch-matrix SPT on dig, notify email + Cliq (qa-agent worker)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from orchestrator.activities.commit_spt import activity_commit_spt


@workflow.defn(name="CommitSptWorkflow")
class CommitSptWorkflow:
    @workflow.run
    async def run(self, args: dict[str, Any]) -> dict[str, Any]:
        tracking_id = str(args.get("tracking_id") or "")
        retry = RetryPolicy(maximum_attempts=2)
        # Main load can exceed 15m (ramp ~2m + full suite).
        timeout = timedelta(minutes=45)

        workflow.logger.info(
            "commit_spt.start tracking_id=%s service=%s branch=%s",
            tracking_id,
            args.get("service"),
            args.get("branch"),
        )
        # Ledger upsert happens inside the activity (sandbox blocks stores/os.environ).
        result = await workflow.execute_activity(
            activity_commit_spt,
            args,
            start_to_close_timeout=timeout,
            retry_policy=retry,
        )
        status = "passed" if result.get("ok") else "failed"
        return {**result, "workflow_status": status}
