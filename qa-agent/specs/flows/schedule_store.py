"""Persist API-flow schedules (cron + env + credential) under data_dir."""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any

from specs.config import settings

_LOCK = threading.Lock()
_CRON_RE = re.compile(
    r"^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$"
)


class ScheduleError(ValueError):
    pass


def _path() -> Path:
    return Path(settings.data_dir) / "qa_flow_schedules.json"


def _empty() -> dict[str, Any]:
    return {"version": 1, "schedules": {}}


def _load() -> dict[str, Any]:
    path = _path()
    if not path.is_file():
        return _empty()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty()
    if not isinstance(raw, dict):
        return _empty()
    schedules = raw.get("schedules")
    if not isinstance(schedules, dict):
        schedules = {}
    return {"version": int(raw.get("version") or 1), "schedules": schedules}


def _save(data: dict[str, Any]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    with _LOCK:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)


def validate_cron(cron: str) -> str:
    s = (cron or "").strip()
    if not _CRON_RE.match(s):
        raise ScheduleError(
            f"Invalid cron {cron!r}; expect 5 fields (min hour dom month dow)"
        )
    return s


def list_schedules(*, flow_id: str | None = None) -> list[dict[str, Any]]:
    data = _load()
    rows = [dict(v) for v in (data.get("schedules") or {}).values() if isinstance(v, dict)]
    if flow_id:
        rows = [r for r in rows if r.get("flow_id") == flow_id]
    return sorted(rows, key=lambda r: str(r.get("id") or ""))


def get_schedule(schedule_id: str) -> dict[str, Any] | None:
    data = _load()
    rec = (data.get("schedules") or {}).get(schedule_id)
    return dict(rec) if isinstance(rec, dict) else None


def upsert_schedule(
    *,
    flow_id: str,
    cron: str,
    env: str = "prod",
    credential_id: str | None = None,
    enabled: bool = True,
    schedule_id: str | None = None,
) -> dict[str, Any]:
    from specs.flows.catalog import get_flow

    fid = (flow_id or "").strip()
    if not fid or not get_flow(fid):
        raise ScheduleError(f"flow not found: {fid}")
    cron_n = validate_cron(cron)
    sid = (schedule_id or f"sched-{fid}").strip()
    sid = re.sub(r"[^A-Za-z0-9_.:-]+", "-", sid)[:120]
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    data = _load()
    schedules = dict(data.get("schedules") or {})
    prev = dict(schedules.get(sid) or {})
    rec = {
        "id": sid,
        "flow_id": fid,
        "cron": cron_n,
        "env": (env or "prod").strip().lower(),
        "credential_id": credential_id,
        "enabled": bool(enabled),
        "temporal_schedule_id": prev.get("temporal_schedule_id") or f"qa-flow-{sid}",
        "last_execution_id": prev.get("last_execution_id"),
        "last_run_at": prev.get("last_run_at"),
        "last_error": prev.get("last_error"),
        "backend": prev.get("backend") or "pending",
        "updated_at": now,
        "created_at": prev.get("created_at") or now,
    }
    schedules[sid] = rec
    data["schedules"] = schedules
    _save(data)
    return dict(rec)


def set_schedule_meta(
    schedule_id: str,
    *,
    backend: str | None = None,
    last_execution_id: str | None = None,
    last_run_at: str | None = None,
    last_error: str | None = None,
    enabled: bool | None = None,
) -> dict[str, Any] | None:
    data = _load()
    schedules = dict(data.get("schedules") or {})
    rec = schedules.get(schedule_id)
    if not isinstance(rec, dict):
        return None
    if backend is not None:
        rec["backend"] = backend
    if last_execution_id is not None:
        rec["last_execution_id"] = last_execution_id
    if last_run_at is not None:
        rec["last_run_at"] = last_run_at
    if last_error is not None:
        rec["last_error"] = last_error
    if enabled is not None:
        rec["enabled"] = bool(enabled)
    rec["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    schedules[schedule_id] = rec
    data["schedules"] = schedules
    _save(data)
    return dict(rec)


def disable_schedule(schedule_id: str) -> dict[str, Any] | None:
    return set_schedule_meta(schedule_id, enabled=False)


def delete_schedule(schedule_id: str) -> bool:
    data = _load()
    schedules = dict(data.get("schedules") or {})
    if schedule_id not in schedules:
        return False
    del schedules[schedule_id]
    data["schedules"] = schedules
    _save(data)
    return True
