"""Map ui-test-agent status / report JSON into SPT traces.json + api-index rows."""
from __future__ import annotations

import json
import re
from typing import Any


def _slug(value: str, *, fallback: str = "step") -> str:
    s = re.sub(r"[^a-zA-Z0-9_\-]+", "_", str(value or "").strip())
    s = s.strip("_") or fallback
    return s[:80]


def _json_body(value: Any) -> str:
    """SPT redact_trace stringifies bodies — store JSON text so inspector can beautify."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, indent=2, default=str)


def _action_by_step(action_log: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Best-effort group action_log entries under step names when present."""
    by: dict[str, list[dict[str, Any]]] = {}
    current = "_run"
    for entry in action_log or []:
        if not isinstance(entry, dict):
            continue
        name = entry.get("step") or entry.get("name") or entry.get("step_name")
        if name:
            current = str(name)
        by.setdefault(current, []).append(entry)
    return by


def map_status_to_traces(
    status: dict[str, Any],
    *,
    report: dict[str, Any] | None = None,
    profile: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """
    Returns (traces, api_index, ui_summary).

    Prefer step_timings; fall back to action_log; suite results become one row per profile.
    """
    report = report or {}
    profile = profile or status.get("profile") or report.get("profile") or "UI_FLOW"
    step_timings = list(status.get("step_timings") or report.get("step_timings") or [])
    action_log = list(status.get("action_log") or report.get("action_log") or [])
    failures = list(status.get("failures") or [])
    soft = list(status.get("soft_failures") or [])
    console_errors = list(status.get("console_errors") or [])
    design = status.get("design_review") or report.get("design_review") or {}

    # Suite aggregate: one synthetic step per child profile
    suite_results = status.get("results")
    if isinstance(suite_results, list) and suite_results and not step_timings:
        traces: list[dict[str, Any]] = []
        for i, child in enumerate(suite_results):
            if not isinstance(child, dict):
                continue
            pname = str(child.get("profile") or f"profile_{i}")
            ok = str(child.get("status") or "").upper() in ("COMPLETED", "GO", "GO_WITH_CAVEATS")
            soft_n = len(child.get("soft_failures") or [])
            traces.append(
                {
                    "kind": "ui_step",
                    "call_index": i + 1,
                    "api_id": _slug(pname, fallback=f"profile_{i}"),
                    "name": pname,
                    "method": "SUITE",
                    "path": f"/{_slug(pname)}",
                    "url": status.get("targetUrl") or report.get("target_url") or "",
                    "vu": 1,
                    "iter": 0,
                    "request": {
                        "headers": {"x-ui-profile": pname},
                        "body": _json_body(
                            {
                                "profile": pname,
                                "report": child.get("report"),
                            }
                        ),
                    },
                    "response": {
                        "status": 200 if ok else 500,
                        "headers": {},
                        "body": _json_body(
                            {
                                "status": child.get("status"),
                                "error": child.get("error"),
                                "soft_failures": child.get("soft_failures") or [],
                                "duration_ms": child.get("duration_ms"),
                            }
                        ),
                    },
                    "timings": {"duration_ms": child.get("duration_ms")},
                    "checks_passed": ok and soft_n == 0,
                }
            )
        index = _index_from_traces(traces)
        summary = {
            "kind": "suite",
            "decision": status.get("decision"),
            "suite": status.get("suite"),
            "hard_fail_count": status.get("hard_fail_count"),
            "soft_fail_count": status.get("soft_fail_count"),
            "profile_count": len(traces),
            "ui_test_id": status.get("testId"),
            "report_html_url": status.get("reportUrl"),
            "report_json_url": status.get("reportJsonUrl"),
            "trace_url": status.get("traceUrl"),
            "release_gate": report.get("release_gate"),
            "llm_report": report.get("llm_report"),
            "timing": report.get("timing") or {"total_ms": status.get("duration_ms")},
        }
        return traces, index, summary

    actions_by = _action_by_step(action_log)
    fail_msgs = []
    for f in failures:
        if isinstance(f, dict):
            fail_msgs.append(str(f.get("error") or f.get("message") or f))
        else:
            fail_msgs.append(str(f))
    soft_msgs = []
    for f in soft:
        if isinstance(f, dict):
            soft_msgs.append(str(f.get("error") or f.get("message") or f))
        else:
            soft_msgs.append(str(f))

    traces = []
    if step_timings:
        for i, row in enumerate(step_timings):
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or f"step_{i + 1}")
            action = str(row.get("action") or "STEP").upper()
            st = str(row.get("status") or "ok").lower()
            ok = st in ("ok", "pass", "passed", "completed")
            err = row.get("error")
            if err:
                ok = False
            related = actions_by.get(name) or actions_by.get("_run") or []
            # Match failure text to this step when possible
            step_fail = [
                m
                for m in fail_msgs
                if name.lower() in m.lower() or action.lower() in m.lower()
            ]
            if step_fail:
                ok = False
            api_id = _slug(f"{profile}_{name}", fallback=f"step_{i + 1}")
            shot = row.get("screenshot_url")
            trace_row: dict[str, Any] = {
                "kind": "ui_step",
                "call_index": int(row.get("index") or i + 1),
                "api_id": api_id,
                "name": name,
                "method": action[:24] or "STEP",
                "path": f"/{_slug(name)}",
                "url": status.get("targetUrl")
                or report.get("target_url")
                or (report.get("results") or {}).get("final_url")
                or "",
                "vu": 1,
                "iter": 0,
                "request": {
                    "headers": {
                        "x-ui-profile": str(profile),
                        "x-ui-phase": str(row.get("phase") or ""),
                    },
                    "body": _json_body(
                        {
                            "step": row,
                            "actions": related[-10:],
                        }
                    ),
                },
                "response": {
                    "status": 200 if ok else 500,
                    "headers": {},
                    "body": _json_body(
                        {
                            "status": st,
                            "error": err or (step_fail[0] if step_fail else None),
                            "soft_failures": soft_msgs[:5] if not ok else [],
                            "console_errors": console_errors[:5] if not ok else [],
                            "design_review": design if i == len(step_timings) - 1 else None,
                        }
                    ),
                },
                "timings": {"duration_ms": row.get("duration_ms")},
                "checks_passed": ok,
            }
            if shot:
                trace_row["screenshot_url"] = str(shot)
            traces.append(trace_row)
    elif action_log:
        for i, entry in enumerate(action_log):
            if not isinstance(entry, dict):
                continue
            action = str(entry.get("action") or "ACTION").upper()
            name = str(entry.get("name") or entry.get("step") or action)
            traces.append(
                {
                    "kind": "ui_step",
                    "call_index": i + 1,
                    "api_id": _slug(f"{profile}_{name}_{i}", fallback=f"action_{i}"),
                    "name": name,
                    "method": action[:24],
                    "path": f"/{_slug(name)}",
                    "url": str(entry.get("url") or status.get("targetUrl") or ""),
                    "vu": 1,
                    "iter": 0,
                    "request": {"headers": {}, "body": _json_body(entry)},
                    "response": {
                        "status": 200,
                        "headers": {},
                        "body": _json_body({"ok": True}),
                    },
                    "timings": {"duration_ms": entry.get("duration_ms")},
                    "checks_passed": True,
                }
            )
    else:
        # Single summary row so inspector is never empty
        agent_status = str(status.get("status") or "").upper()
        ok = agent_status in ("COMPLETED", "GO", "GO_WITH_CAVEATS") and not fail_msgs
        traces.append(
            {
                "kind": "ui_step",
                "call_index": 1,
                "api_id": _slug(str(profile)),
                "name": str(profile),
                "method": "FLOW",
                "path": f"/{_slug(str(profile))}",
                "url": status.get("targetUrl") or report.get("target_url") or "",
                "vu": 1,
                "iter": 0,
                "request": {
                    "headers": {},
                    "body": _json_body(
                        {"profile": profile, "session_id": status.get("sessionId")}
                    ),
                },
                "response": {
                    "status": 200 if ok else 500,
                    "headers": {},
                    "body": _json_body(
                        {
                            "status": status.get("status"),
                            "error": status.get("error")
                            or (fail_msgs[0] if fail_msgs else None),
                            "failures": fail_msgs,
                            "soft_failures": soft_msgs,
                            "console_errors": console_errors[:10],
                            "design_review": design,
                        }
                    ),
                },
                "timings": {"duration_ms": status.get("duration_ms")},
                "checks_passed": ok,
            }
        )

    index = _index_from_traces(traces)
    summary = {
        "kind": "profile",
        "profile": profile,
        "status": status.get("status"),
        "session_id": status.get("sessionId"),
        "ui_test_id": status.get("testId") or report.get("test_id"),
        "report_html_url": status.get("reportUrl"),
        "report_json_url": status.get("reportJsonUrl"),
        "trace_url": status.get("traceUrl"),
        "duration_ms": status.get("duration_ms"),
        "failure_count": len(failures),
        "soft_failure_count": len(soft),
        "release_gate": report.get("release_gate"),
        "llm_report": report.get("llm_report"),
        "timing": report.get("timing"),
        "design_review": design,
        "console_errors": console_errors[:20],
    }
    return traces, index, summary


def _index_from_traces(traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by: dict[str, dict[str, Any]] = {}
    for t in traces:
        api_id = str(t.get("api_id") or "step")
        row = by.setdefault(
            api_id,
            {
                "api_id": api_id,
                "name": t.get("name") or api_id,
                "method": t.get("method") or "STEP",
                "path": t.get("path") or "",
                "trace_available": True,
                "checks_passed": True,
                "request_count": 0,
                "pass_count": 0,
                "fail_count": 0,
                "status": "done",
                "kind": "ui_step",
            },
        )
        row["request_count"] = int(row.get("request_count") or 0) + 1
        ok = t.get("checks_passed")
        if ok is False:
            row["checks_passed"] = False
            row["fail_count"] = int(row.get("fail_count") or 0) + 1
        elif ok is True:
            row["pass_count"] = int(row.get("pass_count") or 0) + 1
        ms = (t.get("timings") or {}).get("duration_ms")
        if ms is not None:
            try:
                cur = row.get("duration_ms")
                val = float(ms)
                row["duration_ms"] = val if cur is None else round((float(cur) + val) / 2, 2)
            except (TypeError, ValueError):
                pass
    return list(by.values())


def agent_status_passed(status: dict[str, Any]) -> bool:
    s = str(status.get("status") or "").upper()
    if s in ("FAILED", "NO_GO"):
        return False
    if status.get("failures"):
        return False
    if s in (
        "COMPLETED",
        "GO",
        "GO_WITH_CAVEATS",
        "PASSED",
        "PASS",
        "OK",
        "PASSED_WITH_DESIGN_DRIFT",
    ):
        return True
    return False
