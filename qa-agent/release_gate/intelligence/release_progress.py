"""Build release progress view for GHA / portal (Temporal SoT + ledger steps)."""

from __future__ import annotations

from typing import Any

from stores import get_ledger

_PHASE_ORDER = (
    "release_ops_init",
    "release_ops_wait_deploy_healthy",
    "release_ops_ui_suite",
    "release_ops_pack_t0",
    "release_ops_stability_score",
    "release_ops_publish_sheet",
    "release_ops_publish_drive",
    "release_ops_cliq_final",
    "release_ops_complete",
)


def build_progress_from_ledger(tracking_id: str) -> dict[str, Any]:
    run = get_ledger().get(tracking_id) if tracking_id else None
    if not run:
        return {
            "phase": "unknown",
            "status": "unknown",
            "pending": [],
            "blockers": [],
            "ui_pct": 0,
            "services": [],
            "steps": [],
        }

    steps = run.steps or {}
    done = [s for s in _PHASE_ORDER if s in steps]
    phase = done[-1] if done else "release_ops_init"
    wait = steps.get("release_ops_wait_deploy_healthy") or {}
    ui = steps.get("release_ops_ui_suite") or {}
    pending = list(wait.get("pending") or [])
    blockers = list(wait.get("blockers") or [])

    ui_pct = 0
    if ui.get("decision") == "SKIPPED":
        ui_pct = 100
    elif ui.get("decision") in {"GO", "GO_WITH_CAVEATS", "NO_GO"} or ui.get("results") is not None:
        ui_pct = 100
    elif "release_ops_ui_suite" in steps:
        ui_pct = 50

    status = run.status or "running"
    if "release_ops_complete" in steps:
        status = str((steps.get("release_ops_complete") or {}).get("status") or status)

    return {
        "phase": phase,
        "status": status,
        "pending": pending,
        "blockers": blockers,
        "ui_pct": ui_pct,
        "services": pending,
        "steps": done,
        "workflow_id": run.workflow_id,
        "tracking_id": tracking_id,
        "first_check_ok": bool(wait.get("ok")) if wait else None,
        "ui_decision": ui.get("decision"),
    }


def enrich_release_view(req_dict: dict[str, Any]) -> dict[str, Any]:
    """Merge pending-request row with ledger progress for GET /v2/releases/{id}."""
    tracking_id = str(req_dict.get("tracking_id") or "")
    progress = build_progress_from_ledger(tracking_id)
    return {
        **req_dict,
        "phase": progress.get("phase"),
        "progress_status": progress.get("status"),
        "pending": progress.get("pending") or [],
        "blockers": progress.get("blockers") or [],
        "ui_pct": progress.get("ui_pct") or 0,
        "services": progress.get("services") or [],
        "steps_done": progress.get("steps") or [],
        "first_check_ok": progress.get("first_check_ok"),
        "ui_decision": progress.get("ui_decision"),
    }


def resolve_release_view(request_id: str) -> dict[str, Any] | None:
    """Pending-store first; fall back to ledger by workflow_id / tracking_id.

    Survives in-memory pending loss when DATA_DIR file is missing but ledger
    still has ``asrax-release-ops-{request_id}`` (ops/start convention).
    """
    from intelligence.cliq_release_gate import get_pending_store

    rid = (request_id or "").strip()
    if not rid:
        return None

    req = get_pending_store().get(rid)
    if req:
        return enrich_release_view(req.to_dict())

    ledger = get_ledger()
    run = None
    find_wf = getattr(ledger, "find_by_workflow_id", None)
    if callable(find_wf):
        run = find_wf(f"asrax-release-ops-{rid}")
    if run is None and rid.startswith("qa-"):
        run = ledger.get(rid)
    if run is None:
        return None

    meta = dict(run.meta or {})
    init = (run.steps or {}).get("release_ops_init") or {}
    summary = init.get("summary") if isinstance(init.get("summary"), dict) else {}
    base = {
        "request_id": str(meta.get("request_id") or rid),
        "status": run.status or "started",
        "tracking_id": run.tracking_id,
        "workflow_id": run.workflow_id,
        "release_id": str(meta.get("release_id") or summary.get("release_id") or ""),
        "release_name": str(meta.get("release_name") or summary.get("release_id") or ""),
        "env": str(summary.get("env") or meta.get("env") or "prod"),
        "suite": str(summary.get("suite") or meta.get("suite") or "prod_ui_full"),
        "target_url": str(summary.get("target_url") or meta.get("target_url") or ""),
        "source": "ledger_fallback",
    }
    return enrich_release_view(base)
