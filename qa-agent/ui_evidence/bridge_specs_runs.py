"""Progressive Specs /api/runs bridge for suite profiles (portal visibility mid-run)."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# UI-evidence / Playwright statuses that mean the scenario passed.
_PASS_STATUSES = frozenset(
    {
        "PASSED",
        "PASS",
        "OK",
        "GO",
        "COMPLETED",
        "PASSED_WITH_DESIGN_DRIFT",
        "GO_WITH_CAVEATS",
    }
)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ui_status_passed(status: str | None) -> bool:
    return str(status or "").strip().upper() in _PASS_STATUSES


def load_profile_report_json(row: dict[str, Any]) -> dict[str, Any] | None:
    """Load per-profile Playwright report JSON from row.report / report_html_path."""
    report_html = str(row.get("report") or row.get("report_html_path") or "").strip()
    if not report_html:
        return None
    json_path = Path(report_html).with_suffix(".json")
    if not json_path.is_file():
        # Sometimes report already points at .json
        candidate = Path(report_html)
        if candidate.suffix.lower() == ".json" and candidate.is_file():
            json_path = candidate
        else:
            return None
    try:
        loaded = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("bridge load report json failed path=%s err=%s", json_path, exc)
        return None
    return loaded if isinstance(loaded, dict) else None


def build_enriched_ui_evidence(
    row: dict[str, Any],
    *,
    run_id: str,
    profile: str,
    target_url: str = "",
) -> dict[str, Any]:
    """
    Map child report JSON → traces + api_summary + rich ui_report.

    Returns keys ready to merge into save_run:
      ui_report, api_summary, api_count, api_pass_count, api_fail_count,
      ui_report_html_url, passed (from report status when available)
    """
    from specs.persistence.artifact_store import portal_artifact_url
    from specs.persistence.trace_store import save_api_index, save_traces_file
    from specs.ui_bridge.ui_trace_mapper import map_status_to_traces

    report = load_profile_report_json(row) or {}
    status_payload: dict[str, Any] = {
        "status": report.get("status") or row.get("status"),
        "profile": profile or report.get("profile"),
        "testId": report.get("test_id"),
        "sessionId": report.get("session_id"),
        "targetUrl": report.get("target_url") or target_url or row.get("target_url"),
        "duration_ms": report.get("timing", {}).get("total_duration_ms")
        if isinstance(report.get("timing"), dict)
        else row.get("duration_ms"),
        "step_timings": report.get("step_timings") or [],
        "action_log": report.get("action_log") or [],
        "failures": (report.get("results") or {}).get("failures")
        if isinstance(report.get("results"), dict)
        else [],
        "soft_failures": report.get("soft_failures")
        if isinstance(report.get("soft_failures"), list)
        else [],
        "console_errors": report.get("console_errors") or [],
        "design_review": report.get("design_review") or {},
        "reportUrl": report.get("report_html"),
        "reportJsonUrl": report.get("report_json_path"),
    }
    # Nested checklist on results
    results = report.get("results") if isinstance(report.get("results"), dict) else {}
    if not status_payload["failures"] and results.get("failures"):
        status_payload["failures"] = list(results.get("failures") or [])

    traces, api_index, ui_summary = map_status_to_traces(
        status_payload,
        report=report,
        profile=profile,
    )

    # Persist under Specs DATA_DIR artifacts/{run_id}/
    try:
        from specs.config import settings as specs_settings

        art_dir = Path(specs_settings.data_dir) / "artifacts" / run_id
    except Exception:  # noqa: BLE001
        art_dir = Path("data") / "artifacts" / run_id
    art_dir.mkdir(parents=True, exist_ok=True)
    save_traces_file(art_dir / "traces.json", traces)
    save_api_index(art_dir / "api-index.json", api_index)

    report_html = str(row.get("report") or "").strip()
    html_path = Path(report_html) if report_html else None
    ui_report: dict[str, Any] = {
        **ui_summary,
        "profile": profile,
        "status": status_payload.get("status"),
        "duration_ms": status_payload.get("duration_ms") or row.get("duration_ms"),
        "soft_failure_count": row.get("soft_failures")
        if row.get("soft_failures") is not None
        else report.get("soft_failure_count")
        or (results.get("checklist_fail") if results else None),
        "error": row.get("error"),
        "report_html_path": report_html or None,
        "step_timings": status_payload.get("step_timings") or [],
        "checklist": results.get("checklist") if results else report.get("checklist"),
        "timing": report.get("timing"),
        "release_gate": report.get("release_gate"),
        "llm_report": report.get("llm_report"),
    }
    if html_path and html_path.suffix.lower() == ".html":
        ui_report["ui_test_id"] = html_path.stem
        json_path = html_path.with_suffix(".json")
        if json_path.is_file():
            ui_report["report_json_path"] = str(json_path)
    elif report.get("test_id"):
        ui_report["ui_test_id"] = report.get("test_id")
        ui_report["report_json_path"] = str(
            Path(report_html).with_suffix(".json")
        ) if report_html else None

    # Prefer SPT virtual artifact URL (portal serves from traces when present)
    ui_report_html_url = portal_artifact_url(run_id, "ui-report.html")

    pass_n = len([a for a in api_index if a.get("checks_passed")])
    fail_n = len([a for a in api_index if a.get("checks_passed") is False])
    report_status = str(status_payload.get("status") or row.get("status") or "")
    return {
        "ui_report": ui_report,
        "api_summary": api_index,
        "api_count": len(api_index),
        "api_pass_count": pass_n,
        "api_fail_count": fail_n,
        "ui_report_html_url": ui_report_html_url,
        "passed": ui_status_passed(report_status),
        "status_label": report_status,
    }


def _ui_report_thin(row: dict[str, Any]) -> dict[str, Any]:
    """Fallback thin ui_report when enrichment imports fail."""
    profile = str(row.get("profile") or "")
    status = str(row.get("status") or "")
    report_html = str(row.get("report") or "").strip()
    report: dict[str, Any] = {
        "profile": profile,
        "status": status,
        "duration_ms": row.get("duration_ms"),
        "soft_failure_count": row.get("soft_failures"),
        "error": row.get("error"),
        "report_html_path": report_html or None,
    }
    loaded = load_profile_report_json(row)
    if loaded:
        for k in (
            "profile",
            "status",
            "duration_ms",
            "failure_count",
            "soft_failure_count",
            "checklist",
            "step_timings",
        ):
            if k in loaded:
                report[k] = loaded[k]
        report["report_json_path"] = str(
            Path(report_html).with_suffix(".json")
        ) if report_html else None
        if report_html:
            report["ui_test_id"] = Path(report_html).stem
    return report


def bridge_suite_profile_run(
    *,
    tracking_id: str,
    profile: str,
    row: dict[str, Any],
    suite: str = "auth_user_module",
    env: str = "prod",
    target_url: str = "https://am.asrax.in",
    workflow_id: str = "",
    release_id: str = "",
    requested_by: str = "asrax-release-ops",
) -> str | None:
    """Upsert one scenario/profile row so portal Shows it before suite end."""
    if not tracking_id or not profile:
        return None
    try:
        from specs.persistence.run_store import save_run
    except Exception as exc:  # noqa: BLE001
        logger.warning("bridge_specs import failed: %s", exc)
        return None

    suite_id = f"relops-{tracking_id}"
    pid = f"relops-{tracking_id}-{profile}".replace(" ", "_")[:120]
    prow_status = str(row.get("status") or "").upper()
    now = _utc()

    evidence: dict[str, Any] = {}
    try:
        evidence = build_enriched_ui_evidence(
            {**row, "profile": profile},
            run_id=pid,
            profile=profile,
            target_url=target_url,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("bridge enrich failed profile=%s err=%s", profile, exc)
        evidence = {
            "ui_report": _ui_report_thin({**row, "profile": profile}),
            "api_summary": [],
            "api_count": 0,
            "api_pass_count": 0,
            "api_fail_count": 0,
            "ui_report_html_url": None,
            "passed": ui_status_passed(prow_status),
            "status_label": prow_status,
        }

    prow_pass = bool(evidence.get("passed"))
    if evidence.get("status_label"):
        prow_status = str(evidence["status_label"]).upper()

    # Ensure parent suite row exists (in-progress)
    try:
        save_run(
            {
                "id": suite_id,
                "started_at": now,
                "finished_at": None,
                "status": "running",
                "passed": False,
                "runner": "asrax-release-ops",
                "run_profile": "release",
                "config_name": suite,
                "service": "am-modern-ui",
                "environment": env,
                "test_type": "playwright",
                "audience": "ci",
                "triggered_by": requested_by,
                "target_url": target_url,
                "tracking_id": tracking_id,
                "workflow_id": workflow_id,
                "release_id": release_id,
                "suite": suite,
                "live": {
                    "phase": "release_ops_ui_suite",
                    "message": f"running {profile}",
                    "pct": 50,
                },
                "ui_report": {"profile": suite, "status": "running", "suite": suite},
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("bridge suite stub failed: %s", exc)

    try:
        rec: dict[str, Any] = {
            "id": pid,
            "started_at": now,
            "finished_at": now,
            "status": "passed" if prow_pass else "failed",
            "passed": prow_pass,
            "runner": "asrax-release-ops",
            "run_profile": "release",
            "config_name": profile,
            "service": "am-modern-ui",
            "environment": env,
            "test_type": "playwright",
            "audience": "ci",
            "triggered_by": requested_by,
            "target_url": target_url,
            "tracking_id": tracking_id,
            "workflow_id": workflow_id,
            "release_id": release_id,
            "suite": suite,
            "parent_run_id": suite_id,
            "ui_report": evidence.get("ui_report")
            or _ui_report_thin({**row, "profile": profile}),
            "api_summary": evidence.get("api_summary") or [],
            "api_count": evidence.get("api_count") or 0,
            "api_pass_count": evidence.get("api_pass_count") or 0,
            "api_fail_count": evidence.get("api_fail_count") or 0,
            "live": {"phase": "profile", "message": profile, "pct": 100},
            "error": None if prow_pass else prow_status,
        }
        if evidence.get("ui_report_html_url"):
            rec["ui_report_html_url"] = evidence["ui_report_html_url"]
        out = save_run(rec)
        rid = str(out.get("id") or pid)
        logger.info(
            "bridge_specs profile=%s id=%s status=%s api_count=%s",
            profile,
            rid,
            prow_status,
            rec.get("api_count"),
        )
        return rid
    except Exception as exc:  # noqa: BLE001
        logger.warning("bridge profile failed profile=%s err=%s", profile, exc)
        return None
