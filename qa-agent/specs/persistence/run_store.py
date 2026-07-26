"""Store facade — routes to JSON / DB / dual-write based on SPT_STORE."""

from __future__ import annotations

from typing import Any

from specs.persistence.db.engine import store_mode
from specs.persistence.stores import db_backend as db
from specs.persistence.stores import json_backend as jb

# Re-export helpers used elsewhere
api_outcome_counts = jb.api_outcome_counts
slim_run_for_list = jb.slim_run_for_list


def _mode() -> str:
    return store_mode()


def list_runs(**kwargs: Any) -> tuple[list[dict[str, Any]], int]:
    mode = _mode()
    if mode == "json":
        rows, total = jb.list_runs(**kwargs)
    else:
        rows, total = db.list_runs(**kwargs)
        if mode == "dual" and total == 0:
            # Fallback if DB empty / miss during cutover
            jrows, jtotal = jb.list_runs(**kwargs)
            if jtotal:
                rows, total = jrows, jtotal
    return [normalize_run_view(r) or r for r in rows], total


def get_run(run_id: str) -> dict[str, Any] | None:
    mode = _mode()
    if mode == "json":
        row = jb.get_run(run_id)
    else:
        row = db.get_run(run_id)
        if row is None and mode == "dual":
            row = jb.get_run(run_id)
    return normalize_run_view(row)


def normalize_run_view(row: dict[str, Any] | None) -> dict[str, Any] | None:
    """Coerce contradictory run fields for API/UI (stop race leftovers)."""
    if not row:
        return row
    out = dict(row)
    status = str(out.get("status") or "").lower()
    finished = out.get("finished_at")
    err = str(out.get("error") or "").lower()
    # finished_at + running = stop/progress race — never show as live
    if finished and status in {"running", "pending"}:
        if "stopped" in err or "cancel" in err:
            out["status"] = "cancelled"
        else:
            out["status"] = "failed" if out.get("passed") is False else "cancelled"
        status = str(out["status"])
        live = dict(out.get("live") or {})
        live["phase"] = "cancelled" if status == "cancelled" else "done"
        live["message"] = out.get("error") or ("Stopped by user" if status == "cancelled" else "Finished")
        live.pop("ui_status", None)
        out["live"] = live
    # Keep steps from advertising a live k6 while terminal
    if status in {"cancelled", "failed", "passed", "completed", "error"}:
        steps = out.get("steps")
        if isinstance(steps, list) and steps:
            fixed = []
            for s in steps:
                if not isinstance(s, dict):
                    fixed.append(s)
                    continue
                st = dict(s)
                if str(st.get("status") or "").lower() == "running":
                    st["status"] = "fail" if status in {"cancelled", "failed", "error"} else "pass"
                fixed.append(st)
            out["steps"] = fixed
    # Strip ROOT_PATH from portal-relative artifact URLs (apiBase already has /spt-poc)
    rid = str(out.get("id") or "")
    if rid:
        out["ui_report_html_url"] = _portal_rel_artifact_url(out.get("ui_report_html_url"), rid)
        out["ui_report_pdf_url"] = _portal_rel_artifact_url(out.get("ui_report_pdf_url"), rid)
    return out


def _portal_rel_artifact_url(url: Any, run_id: str) -> Any:
    if not isinstance(url, str) or not url:
        return url
    # Absolute agent URLs stay as-is
    if url.startswith("http") and "/api/runs/" not in url:
        return url
    # /spt-poc/api/runs/... or full https://.../spt-poc/api/runs/... → /api/runs/...
    marker = f"/api/runs/{run_id}/"
    idx = url.find(marker)
    if idx >= 0:
        return url[idx:]
    return url


def save_run(record: dict[str, Any]) -> dict[str, Any]:
    mode = _mode()
    if mode == "json":
        return jb.save_run(record)
    if mode == "dual":
        saved = db.save_run(record)
        try:
            jb.save_run(dict(saved))
        except Exception:
            pass
        return saved
    return db.save_run(record)


def update_run(run_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    mode = _mode()
    if mode == "json":
        return jb.update_run(run_id, patch)
    if mode == "dual":
        row = db.update_run(run_id, patch)
        try:
            jb.update_run(run_id, patch)
        except Exception:
            pass
        if row is None:
            return jb.update_run(run_id, patch)
        return row
    return db.update_run(run_id, patch)


def increment_run_progress(run_id: str, **kwargs: Any) -> dict[str, Any] | None:
    mode = _mode()
    if mode == "json":
        return jb.increment_run_progress(run_id, **kwargs)
    if mode == "dual":
        result = db.increment_run_progress(run_id, **kwargs)
        try:
            jb.increment_run_progress(run_id, **kwargs)
        except Exception:
            pass
        if result and result.get("reason") == "missing":
            return jb.increment_run_progress(run_id, **kwargs)
        return result
    return db.increment_run_progress(run_id, **kwargs)


def list_configs(**kwargs: Any) -> list[dict[str, Any]]:
    mode = _mode()
    if mode == "json":
        return jb.list_configs(**kwargs)
    rows = db.list_configs(**kwargs)
    if mode == "dual" and not rows:
        return jb.list_configs(**kwargs)
    return rows


def get_config(config_id: str) -> dict[str, Any] | None:
    mode = _mode()
    if mode == "json":
        return jb.get_config(config_id)
    row = db.get_config(config_id)
    if row is None and mode == "dual":
        return jb.get_config(config_id)
    return row


def save_config(record: dict[str, Any]) -> dict[str, Any]:
    mode = _mode()
    if mode == "json":
        return jb.save_config(record)
    if mode == "dual":
        saved = db.save_config(record)
        try:
            jb.save_config(dict(saved))
        except Exception:
            pass
        return saved
    return db.save_config(record)


def delete_config(config_id: str) -> bool:
    mode = _mode()
    if mode == "json":
        return jb.delete_config(config_id)
    ok = db.delete_config(config_id)
    if mode == "dual":
        try:
            jb.delete_config(config_id)
        except Exception:
            pass
    return ok


def count_running() -> int:
    mode = _mode()
    if mode == "json":
        rows, _ = jb.list_runs(limit=500, status="running")
        return len(rows)
    return db.count_running()
