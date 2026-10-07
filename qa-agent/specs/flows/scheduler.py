"""Sync flow schedules to Temporal; local tick fallback when Temporal is down."""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_TICKER_STARTED = False
_TICKER_LOCK = threading.Lock()


def _cron_matches_now(cron: str, now: datetime | None = None) -> bool:
    """Minimal 5-field cron match (minute hour dom month dow). Supports * and */N."""
    parts = (cron or "").split()
    if len(parts) != 5:
        return False
    now = now or datetime.now(timezone.utc)
    values = [now.minute, now.hour, now.day, now.month, (now.weekday() + 1) % 7]

    def _match(field: str, value: int) -> bool:
        if field == "*":
            return True
        if field.startswith("*/"):
            try:
                step = int(field[2:])
            except ValueError:
                return False
            return step > 0 and value % step == 0
        try:
            return int(field) == value
        except ValueError:
            return False

    return all(_match(parts[i], values[i]) for i in range(5))


def run_scheduled_flow(schedule: dict[str, Any]) -> dict[str, Any]:
    from specs.flows.runner import start_execution
    from specs.flows import schedule_store as store

    fid = str(schedule.get("flow_id") or "")
    out = start_execution(
        fid,
        env=str(schedule.get("env") or "prod"),
        credential_id=schedule.get("credential_id"),
    )
    eid = out.get("execution_id")
    store.set_schedule_meta(
        str(schedule["id"]),
        last_execution_id=str(eid) if eid else None,
        last_run_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        last_error=None,
    )
    return out


async def sync_schedule_temporal(schedule: dict[str, Any]) -> dict[str, Any]:
    """Create/update/pause a Temporal Schedule that starts FlowExecuteWorkflow."""
    from specs.flows import schedule_store as store

    sid = str(schedule["id"])
    temporal_id = str(schedule.get("temporal_schedule_id") or f"qa-flow-{sid}")
    try:
        from orchestrator.temporal_api import get_temporal_client
        from orchestrator.queue import assert_safe_task_queue, resolve_task_queue
        from temporalio.client import (
            Schedule,
            ScheduleActionStartWorkflow,
            ScheduleSpec,
            ScheduleState,
            ScheduleUpdate,
            ScheduleUpdateInput,
        )
        from orchestrator.workflows.flow_execute import FlowExecuteWorkflow

        client = await get_temporal_client()
        queue = assert_safe_task_queue(resolve_task_queue())
        action = ScheduleActionStartWorkflow(
            FlowExecuteWorkflow.run,
            {
                "flow_id": schedule.get("flow_id"),
                "env": schedule.get("env") or "prod",
                "credential_id": schedule.get("credential_id"),
                "schedule_id": sid,
            },
            id=f"qa-flow-run-{sid}",
            task_queue=queue,
        )
        spec = ScheduleSpec(cron_expressions=[str(schedule.get("cron"))])
        state = ScheduleState(paused=not bool(schedule.get("enabled")))
        handle = client.get_schedule_handle(temporal_id)

        async def _updater(inp: ScheduleUpdateInput) -> ScheduleUpdate:
            return ScheduleUpdate(
                schedule=Schedule(action=action, spec=spec, state=state)
            )

        try:
            await handle.describe()
            await handle.update(_updater)
        except Exception:  # noqa: BLE001
            await client.create_schedule(
                temporal_id,
                Schedule(action=action, spec=spec, state=state),
            )
        store.set_schedule_meta(sid, backend="temporal", last_error=None)
        return {"ok": True, "backend": "temporal", "temporal_schedule_id": temporal_id}
    except Exception as exc:  # noqa: BLE001
        logger.warning("temporal schedule sync failed sid=%s: %s", sid, exc)
        store.set_schedule_meta(sid, backend="local", last_error=str(exc)[:300])
        return {"ok": False, "backend": "local", "error": str(exc)}


def upsert_and_sync(**kwargs: Any) -> dict[str, Any]:
    from concurrent.futures import ThreadPoolExecutor

    from specs.flows import schedule_store as store

    rec = store.upsert_schedule(**kwargs)

    def _sync() -> dict[str, Any]:
        return asyncio.run(sync_schedule_temporal(rec))

    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(_sync).result(timeout=45)
    fresh = store.get_schedule(rec["id"]) or rec
    return {**fresh, "sync": result}


def _local_tick_once(fired: set[str]) -> None:
    from specs.flows import schedule_store as store

    now = datetime.now(timezone.utc)
    minute_key = now.strftime("%Y%m%d%H%M")
    for sched in store.list_schedules():
        if not sched.get("enabled"):
            continue
        if sched.get("backend") == "temporal":
            continue  # Temporal owns firing
        if not _cron_matches_now(str(sched.get("cron") or ""), now):
            continue
        key = f"{sched['id']}:{minute_key}"
        if key in fired:
            continue
        fired.add(key)
        try:
            run_scheduled_flow(sched)
        except Exception as exc:  # noqa: BLE001
            logger.exception("local schedule fire failed")
            store.set_schedule_meta(
                str(sched["id"]),
                last_error=str(exc)[:300],
            )


def start_local_ticker() -> None:
    """Daemon thread: fire local-backend schedules once per matching minute."""
    global _TICKER_STARTED
    with _TICKER_LOCK:
        if _TICKER_STARTED:
            return
        _TICKER_STARTED = True

    def _loop() -> None:
        fired: set[str] = set()
        while True:
            try:
                _local_tick_once(fired)
                if len(fired) > 5000:
                    fired.clear()
            except Exception:  # noqa: BLE001
                logger.exception("schedule ticker error")
            time.sleep(20)

    t = threading.Thread(target=_loop, name="qa-flow-schedule-ticker", daemon=True)
    t.start()
