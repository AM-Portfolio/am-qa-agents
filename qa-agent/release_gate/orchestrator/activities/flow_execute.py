"""Activity: start stepped API flow execution (for Temporal schedules)."""
from __future__ import annotations

import time
from typing import Any

from temporalio import activity


@activity.defn(name="activity_flow_execute")
async def activity_flow_execute(args: dict[str, Any]) -> dict[str, Any]:
    from specs.flows.runner import start_execution
    from specs.flows import schedule_store as store

    flow_id = str(args.get("flow_id") or "")
    out = start_execution(
        flow_id,
        env=str(args.get("env") or "prod"),
        credential_id=args.get("credential_id"),
    )
    sid = args.get("schedule_id")
    if sid:
        store.set_schedule_meta(
            str(sid),
            last_execution_id=str(out.get("execution_id") or "") or None,
            last_run_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            last_error=None,
            backend="temporal",
        )
    return {"ok": True, **out}
