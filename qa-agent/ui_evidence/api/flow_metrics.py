"""Rolling hotspot metrics for auth/user/subscription API flow runs."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def step_key(flow_id: str, step: dict[str, Any]) -> str:
    sid = str(step.get("id") or "step")
    path = str(step.get("path") or "")
    method = str(step.get("method") or "")
    return f"{flow_id}::{sid}::{method}::{path}"


def default_ledger_path(report_dir: Path) -> Path:
    return report_dir / "auth-user-api-flows-metrics.json"


def subscription_ledger_path(report_dir: Path) -> Path:
    return report_dir / "subscription-api-flows-metrics.json"


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"updated_at": None, "steps": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"updated_at": None, "steps": {}}
    if not isinstance(data, dict):
        return {"updated_at": None, "steps": {}}
    steps = data.get("steps")
    if not isinstance(steps, dict):
        data["steps"] = {}
    return data


def save_ledger(path: Path, ledger: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ledger["updated_at"] = _utc()
    path.write_text(json.dumps(ledger, indent=2, default=str), encoding="utf-8")


def merge_flow_results_into_ledger(
    ledger: dict[str, Any],
    flows: list[dict[str, Any]],
) -> dict[str, Any]:
    steps_map: dict[str, Any] = ledger.setdefault("steps", {})
    for flow in flows:
        fid = str(flow.get("id") or "")
        for step in flow.get("steps") or []:
            if not isinstance(step, dict):
                continue
            key = step_key(fid, step)
            row = steps_map.get(key) or {
                "flow_id": fid,
                "step_id": step.get("id"),
                "path": step.get("path"),
                "method": step.get("method"),
                "runs": 0,
                "pass_count": 0,
                "fail_count": 0,
                "expected_count": 0,
                "skip_count": 0,
                "other_count": 0,
                "total_ms": 0.0,
                "max_ms": 0.0,
                "timed_runs": 0,
            }
            status = str(step.get("status") or "").upper()
            row["runs"] = int(row.get("runs") or 0) + 1
            if status == "PASSED":
                row["pass_count"] = int(row.get("pass_count") or 0) + 1
            elif status == "FAILED":
                row["fail_count"] = int(row.get("fail_count") or 0) + 1
            elif status == "EXPECTED":
                row["expected_count"] = int(row.get("expected_count") or 0) + 1
            elif status in {"SKIPPED", "DISCOVERED", "MISSING"}:
                row["skip_count"] = int(row.get("skip_count") or 0) + 1
            else:
                row["other_count"] = int(row.get("other_count") or 0) + 1
            dur = step.get("duration_ms")
            if isinstance(dur, (int, float)) and dur >= 0:
                row["total_ms"] = float(row.get("total_ms") or 0) + float(dur)
                row["timed_runs"] = int(row.get("timed_runs") or 0) + 1
                row["max_ms"] = max(float(row.get("max_ms") or 0), float(dur))
            timed = int(row.get("timed_runs") or 0)
            row["avg_ms"] = (
                round(float(row["total_ms"]) / timed, 1) if timed else None
            )
            if step.get("http_status") is not None:
                row["last_http_status"] = step.get("http_status")
            row["last_status"] = status
            row["last_seen_at"] = _utc()
            steps_map[key] = row
    return ledger


def merge_sweep_into_ledger(
    ledger: dict[str, Any],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Optional: fold OpenAPI sweep rows into the same ledger."""
    steps_map: dict[str, Any] = ledger.setdefault("steps", {})
    for row in results:
        if not isinstance(row, dict):
            continue
        svc = str(row.get("service") or "svc")
        path = str(row.get("path") or "")
        method = str(row.get("method") or "")
        key = f"SWEEP::{svc}::{method}::{path}"
        entry = steps_map.get(key) or {
            "flow_id": "SWEEP",
            "step_id": row.get("tool") or path,
            "path": path,
            "method": method,
            "service": svc,
            "runs": 0,
            "pass_count": 0,
            "fail_count": 0,
            "expected_count": 0,
            "skip_count": 0,
            "other_count": 0,
            "total_ms": 0.0,
            "max_ms": 0.0,
            "timed_runs": 0,
        }
        status = str(row.get("status") or "").upper()
        entry["runs"] = int(entry.get("runs") or 0) + 1
        if status == "PASSED":
            entry["pass_count"] = int(entry.get("pass_count") or 0) + 1
        elif status == "FAILED":
            entry["fail_count"] = int(entry.get("fail_count") or 0) + 1
        elif status == "EXPECTED":
            entry["expected_count"] = int(entry.get("expected_count") or 0) + 1
        elif status == "SKIPPED":
            entry["skip_count"] = int(entry.get("skip_count") or 0) + 1
        else:
            entry["other_count"] = int(entry.get("other_count") or 0) + 1
        dur = row.get("duration_ms")
        if isinstance(dur, (int, float)) and dur >= 0:
            entry["total_ms"] = float(entry.get("total_ms") or 0) + float(dur)
            entry["timed_runs"] = int(entry.get("timed_runs") or 0) + 1
            entry["max_ms"] = max(float(entry.get("max_ms") or 0), float(dur))
        timed = int(entry.get("timed_runs") or 0)
        entry["avg_ms"] = (
            round(float(entry["total_ms"]) / timed, 1) if timed else None
        )
        entry["last_http_status"] = row.get("http_status")
        entry["last_status"] = status
        entry["last_seen_at"] = _utc()
        steps_map[key] = entry
    return ledger


def _rank(
    steps: dict[str, Any],
    *,
    key: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    rows = []
    for k, v in steps.items():
        if not isinstance(v, dict):
            continue
        val = v.get(key)
        if val is None:
            continue
        try:
            num = float(val)
        except (TypeError, ValueError):
            continue
        if num <= 0:
            continue
        rows.append({**v, "key": k, "rank_value": num})
    rows.sort(key=lambda r: float(r["rank_value"]), reverse=True)
    return rows[:limit]


def this_run_metrics(flows: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    timed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for flow in flows:
        fid = str(flow.get("id") or "")
        for step in flow.get("steps") or []:
            if not isinstance(step, dict):
                continue
            st = str(step.get("status") or "UNKNOWN")
            status_counts[st] = status_counts.get(st, 0) + 1
            item = {
                "flow_id": fid,
                "step_id": step.get("id"),
                "path": step.get("path"),
                "method": step.get("method"),
                "status": st,
                "http_status": step.get("http_status"),
                "duration_ms": step.get("duration_ms"),
            }
            if st == "FAILED":
                failed.append(item)
            dur = step.get("duration_ms")
            if isinstance(dur, (int, float)):
                timed.append(item)
    timed.sort(key=lambda r: float(r.get("duration_ms") or 0), reverse=True)
    return {
        "status_counts": status_counts,
        "failed": failed,
        "slowest": timed[:5],
    }


def build_hotspots(
    ledger: dict[str, Any],
    *,
    flows: list[dict[str, Any]] | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    steps = ledger.get("steps") if isinstance(ledger.get("steps"), dict) else {}
    return {
        "by_fail": _rank(steps, key="fail_count", limit=limit),
        "by_skip": _rank(steps, key="skip_count", limit=limit),
        "by_avg_ms": _rank(steps, key="avg_ms", limit=limit),
        "this_run": this_run_metrics(flows or []),
    }


def render_hotspots_html(hotspots: dict[str, Any]) -> str:
    def _table(title: str, rows: list[dict[str, Any]], value_label: str) -> str:
        if not rows:
            return f"<h3>{title}</h3><p class='meta'>none</p>"
        body = []
        for r in rows:
            body.append(
                "<tr>"
                f"<td>{r.get('flow_id')}</td>"
                f"<td>{r.get('step_id')}</td>"
                f"<td>{r.get('method') or ''}</td>"
                f"<td><code>{r.get('path') or ''}</code></td>"
                f"<td>{r.get('rank_value')}</td>"
                f"<td>{r.get('last_status') or ''}</td>"
                "</tr>"
            )
        return (
            f"<h3>{title}</h3>"
            "<table><thead><tr>"
            f"<th>Flow</th><th>Step</th><th>Method</th><th>Path</th>"
            f"<th>{value_label}</th><th>Last</th>"
            "</tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table>"
        )

    this_run = hotspots.get("this_run") or {}
    slow = this_run.get("slowest") or []
    slow_rows = []
    for r in slow:
        slow_rows.append(
            "<tr>"
            f"<td>{r.get('flow_id')}</td>"
            f"<td>{r.get('step_id')}</td>"
            f"<td>{r.get('duration_ms')}</td>"
            f"<td><code>{r.get('path') or ''}</code></td>"
            "</tr>"
        )
    slow_html = (
        "<h3>This run — slowest steps</h3>"
        + (
            "<table><thead><tr><th>Flow</th><th>Step</th><th>ms</th><th>Path</th>"
            "</tr></thead>"
            f"<tbody>{''.join(slow_rows)}</tbody></table>"
            if slow_rows
            else "<p class='meta'>none</p>"
        )
    )
    return (
        "<section class='hotspots'><h2>Hotspots (optimize these first)</h2>"
        + _table("Highest fail count (ledger)", hotspots.get("by_fail") or [], "fails")
        + _table("Highest skip count (ledger)", hotspots.get("by_skip") or [], "skips")
        + _table("Slowest avg_ms (ledger)", hotspots.get("by_avg_ms") or [], "avg_ms")
        + slow_html
        + "</section>"
    )
