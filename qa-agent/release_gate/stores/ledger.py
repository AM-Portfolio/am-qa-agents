"""In-memory workflow ledger for Phase 0 (Postgres in later phases)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WorkflowRun:
    tracking_id: str
    workflow_id: str
    status: str = "running"
    route: str | None = None
    steps: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)


class InMemoryWorkflowLedger:
    def __init__(self) -> None:
        self._runs: dict[str, WorkflowRun] = {}
        self._idem: dict[str, str] = {}
        self._lock = Lock()

    def create_run(
        self,
        *,
        tracking_id: str,
        workflow_id: str,
        idempotency_key: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> WorkflowRun:
        with self._lock:
            if idempotency_key and idempotency_key in self._idem:
                existing = self._runs[self._idem[idempotency_key]]
                return existing
            run = WorkflowRun(
                tracking_id=tracking_id,
                workflow_id=workflow_id,
                meta=meta or {},
            )
            self._runs[tracking_id] = run
            if idempotency_key:
                self._idem[idempotency_key] = tracking_id
            return run

    def upsert_step(self, tracking_id: str, step: str, payload: dict[str, Any]) -> None:
        with self._lock:
            run = self._runs.get(tracking_id)
            if not run:
                return
            run.steps[step] = {**payload, "at": _now()}
            run.updated_at = _now()
            workflow_id = run.workflow_id
        try:
            from common.observability.domain_flow import emit_step_log

            emit_step_log(
                tracking_id=tracking_id,
                step=step,
                payload=payload,
                workflow_id=workflow_id,
            )
        except Exception:  # noqa: BLE001
            pass

    def set_route(self, tracking_id: str, route: str) -> None:
        with self._lock:
            run = self._runs.get(tracking_id)
            if run:
                run.route = route
                run.updated_at = _now()

    def complete(self, tracking_id: str, status: str = "completed") -> None:
        with self._lock:
            run = self._runs.get(tracking_id)
            if run:
                run.status = status
                run.updated_at = _now()

    def get(self, tracking_id: str) -> WorkflowRun | None:
        with self._lock:
            return self._runs.get(tracking_id)

    def find_by_workflow_id(self, workflow_id: str) -> WorkflowRun | None:
        wid = (workflow_id or "").strip()
        if not wid:
            return None
        with self._lock:
            for run in self._runs.values():
                if run.workflow_id == wid:
                    return run
            return None

    def find_by_idempotency(self, key: str) -> WorkflowRun | None:
        with self._lock:
            tid = self._idem.get(key)
            return self._runs.get(tid) if tid else None


_LEDGER = InMemoryWorkflowLedger()


def get_ledger() -> InMemoryWorkflowLedger:
    return _LEDGER
