"""In-memory stepped flow execution state (+ recent history ring)."""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

_LOCK = threading.Lock()
_EXEC: dict[str, dict[str, Any]] = {}
_HISTORY: list[str] = []  # newest last
_HISTORY_MAX = 200


def create_execution(
    flow_id: str,
    *,
    env: str,
    credential_id: str | None,
    variables: dict[str, Any] | None = None,
    payload_set_version: int | None = None,
    suite_run_id: str | None = None,
) -> str:
    eid = uuid.uuid4().hex
    now = time.time()
    raw_vars = {str(k): v for k, v in (variables or {}).items() if str(k).strip()}
    with _LOCK:
        _EXEC[eid] = {
            "id": eid,
            "flow_id": flow_id,
            "env": env,
            "credential_id": credential_id,
            "_variables_raw": raw_vars,
            "variables": _redact_variables(raw_vars),
            "payload_set_version": payload_set_version,
            "suite_run_id": suite_run_id,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "events": [],
            "nodes": {},
            "stop_requested": False,
            "error": None,
            "summary": None,
        }
        _HISTORY.append(eid)
        while len(_HISTORY) > _HISTORY_MAX:
            old = _HISTORY.pop(0)
            # Keep running/recent; only drop terminal olds not referenced
            old_row = _EXEC.get(old)
            if old_row and str(old_row.get("status") or "") in {
                "finished",
                "failed",
                "error",
                "stopped",
            }:
                # Retain row for get_execution until map grows too large
                if len(_EXEC) > _HISTORY_MAX * 2:
                    _EXEC.pop(old, None)
    return eid


def _redact_variables(variables: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in variables.items():
        lk = str(k).lower()
        if any(x in lk for x in ("password", "token", "secret", "authorization")):
            out[str(k)] = "<redacted>"
        else:
            out[str(k)] = v
    return out


def _public_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out.pop("_variables_raw", None)
    out["variables"] = _redact_variables(
        row.get("_variables_raw")
        if isinstance(row.get("_variables_raw"), dict)
        else (row.get("variables") or {})
    )
    return out


def get_execution(eid: str, *, include_raw: bool = False) -> dict[str, Any] | None:
    with _LOCK:
        row = _EXEC.get(eid)
        if not row:
            return None
        if include_raw:
            return dict(row)
        return _public_row(row)


def list_executions(
    *,
    flow_id: str | None = None,
    env: str | None = None,
    status: str | None = None,
    suite_run_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    fid = (flow_id or "").strip() or None
    env_n = (env or "").strip().lower() or None
    st = (status or "").strip().lower() or None
    suite = (suite_run_id or "").strip() or None
    lim = max(1, min(int(limit or 50), 200))
    with _LOCK:
        ids = list(reversed(_HISTORY))  # newest first
        out: list[dict[str, Any]] = []
        for eid in ids:
            row = _EXEC.get(eid)
            if not row:
                continue
            if fid and str(row.get("flow_id") or "") != fid:
                continue
            if env_n and str(row.get("env") or "").lower() != env_n:
                continue
            if st and str(row.get("status") or "").lower() != st:
                continue
            if suite and str(row.get("suite_run_id") or "") != suite:
                continue
            # Slim row for list (no full events)
            out.append(
                {
                    "id": row.get("id"),
                    "flow_id": row.get("flow_id"),
                    "env": row.get("env"),
                    "credential_id": row.get("credential_id"),
                    "status": row.get("status"),
                    "suite_run_id": row.get("suite_run_id"),
                    "payload_set_version": row.get("payload_set_version"),
                    "variables": row.get("variables"),
                    "created_at": row.get("created_at"),
                    "updated_at": row.get("updated_at"),
                    "error": row.get("error"),
                    "summary": row.get("summary"),
                }
            )
            if len(out) >= lim:
                break
        return out


def request_stop(eid: str) -> bool:
    with _LOCK:
        row = _EXEC.get(eid)
        if not row:
            return False
        row["stop_requested"] = True
        row["updated_at"] = time.time()
        return True


def stop_requested(eid: str) -> bool:
    with _LOCK:
        row = _EXEC.get(eid)
        return bool(row and row.get("stop_requested"))


def append_event(eid: str, event: dict[str, Any]) -> None:
    with _LOCK:
        row = _EXEC.get(eid)
        if not row:
            return
        row["events"].append(event)
        row["updated_at"] = time.time()
        nid = event.get("node_id")
        if nid and event.get("type") in {"node_started", "node_finished"}:
            nodes = dict(row.get("nodes") or {})
            cur = dict(nodes.get(nid) or {})
            cur.update({k: v for k, v in event.items() if k != "type"})
            if event.get("type") == "node_started":
                cur["status"] = "running"
            nodes[nid] = cur
            row["nodes"] = nodes
        if event.get("type") == "execution_finished":
            row["status"] = event.get("status") or "finished"
            row["summary"] = event.get("summary")
        elif event.get("type") == "execution_started":
            row["status"] = "running"


def set_error(eid: str, message: str) -> None:
    with _LOCK:
        row = _EXEC.get(eid)
        if not row:
            return
        row["status"] = "error"
        row["error"] = message
        row["updated_at"] = time.time()
