"""Domain-wise release-gate flow helpers for structured logs.

Maps ledger steps / activities / outbound calls onto domains so Loki/Tempo
queries can follow intake → testing → evidence → governance → notify.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Iterator
from urllib.parse import urlparse

from common.observability.logging_setup import get_logger, tracking_id_var

LOG = get_logger("qa.flow")

# Ledger step / activity name → domain
_STEP_DOMAIN: dict[str, str] = {
    "classify": "intake",
    "resolve_load_profile": "intake",
    "await_index": "intake",
    "security_scan": "governance",
    "interpret_change_intent": "testing",
    "build_test_matrix": "testing",
    "ensure_catalog_ready": "testing",
    "fin_data_prep": "testing",
    "execute_matrix": "testing",
    "smoke_ui_test": "testing",
    "dev_handoff": "testing",
    "persist_episode": "testing",
    "collect_comparisons": "evidence",
    "post_test_verify": "evidence",
    "analyze_release": "evidence",
    "publish_pdf": "evidence",
    "awaiting_release": "governance",
    "release_hitl": "governance",
    "ingest_feedback": "governance",
    "evaluate_learning": "governance",
    "record_promotion": "governance",
    "github_check_run": "governance",
    "notify": "notify",
    "complete": "workflow",
    "release_ops_init": "release_ops",
    "release_ops_ui_suite": "release_ops",
    "release_ops_pack_t0": "release_ops",
    "release_ops_soak": "release_ops",
    "release_ops_stability_score": "release_ops",
    "release_ops_publish_sheet": "release_ops",
    "release_ops_publish_drive": "release_ops",
    "release_ops_cliq_final": "release_ops",
    "release_ops_complete": "release_ops",
}

_ACTIVITY_DOMAIN: dict[str, str] = {
    "activity_classify": "intake",
    "activity_resolve_load_profile": "intake",
    "activity_await_index": "intake",
    "activity_security_scan": "governance",
    "activity_interpret_change_intent": "testing",
    "activity_build_test_matrix": "testing",
    "activity_ensure_catalog_ready": "testing",
    "activity_fin_data_prep": "testing",
    "activity_execute_matrix": "testing",
    "activity_smoke_ui_test": "testing",
    "activity_dev_handoff_ticket": "testing",
    "activity_persist_episode": "testing",
    "activity_collect_comparisons": "evidence",
    "activity_post_test_verify": "evidence",
    "activity_analyze_release": "evidence",
    "activity_publish_pdf": "evidence",
    "activity_await_release_hitl": "governance",
    "activity_ingest_hitl_feedback": "governance",
    "activity_evaluate_learning": "governance",
    "activity_record_promotion": "governance",
    "activity_github_check_run": "governance",
    "activity_notify": "notify",
    "activity_release_ops_init": "release_ops",
    "activity_release_ops_ui_suite": "release_ops",
    "activity_release_ops_pack_t0": "release_ops",
    "activity_release_ops_stability_score": "release_ops",
    "activity_release_ops_publish_sheet": "release_ops",
    "activity_release_ops_publish_drive": "release_ops",
    "activity_release_ops_cliq_final": "release_ops",
    "activity_release_ops_complete": "release_ops",
}

# Workflow phase markers (human flow order)
FLOW_PHASES: tuple[str, ...] = (
    "classify",
    "load_profile",
    "index",
    "security",
    "change_intent",
    "matrix",
    "fin_prep",
    "catalog",
    "execute",
    "evidence",
    "analyze",
    "publish",
    "hitl",
    "episode",
    "notify",
    "complete",
)


def domain_for_step(step: str) -> str:
    return _STEP_DOMAIN.get(step, "workflow")


def domain_for_activity(name: str) -> str:
    return _ACTIVITY_DOMAIN.get(name, _STEP_DOMAIN.get(name, "workflow"))


def _compact_status(payload: dict[str, Any] | None) -> str:
    if not payload:
        return ""
    for key in ("status", "decision", "recommendation", "route", "ok", "ready", "mode"):
        val = payload.get(key)
        if val is not None and val != "":
            return str(val)[:120]
    return ""


def _safe_target(url: str) -> str:
    """Host + path only — no query/fragment/credentials."""
    try:
        parsed = urlparse(url)
        path = parsed.path or "/"
        if len(path) > 120:
            path = path[:117] + "..."
        host = parsed.netloc or "unknown"
        return f"{host}{path}"
    except Exception:  # noqa: BLE001
        return (url or "")[:140]


def emit_step_log(
    *,
    tracking_id: str,
    step: str,
    payload: dict[str, Any] | None = None,
    workflow_id: str = "",
    event: str = "step.complete",
) -> None:
    """Emit a domain-tagged step log (paired with ledger upsert_step)."""
    domain = domain_for_step(step)
    status = _compact_status(payload)
    LOG.info(
        "step=%s domain=%s status=%s",
        step,
        domain,
        status or "-",
        extra={
            "event": event,
            "phase": step,
            "domain": domain,
            "flow": f"{domain}.{step}",
            "workflow_id": workflow_id,
            "status": status,
            "tracking_id": tracking_id or tracking_id_var.get() or "",
        },
    )


def emit_flow_phase(
    *,
    phase: str,
    tracking_id: str = "",
    route: str = "",
    detail: str = "",
    workflow_id: str = "",
) -> None:
    """Workflow / inline phase boundary (domain-wise flow marker)."""
    domain = domain_for_step(phase) if phase in _STEP_DOMAIN else (
        "intake" if phase in {"classify", "load_profile", "index"}
        else "testing" if phase in {"security", "change_intent", "matrix", "fin_prep", "catalog", "execute"}
        else "evidence" if phase in {"evidence", "analyze", "publish"}
        else "governance" if phase in {"hitl", "episode"}
        else "notify" if phase == "notify"
        else "workflow"
    )
    msg = f"flow.phase={phase} domain={domain}"
    if route:
        msg += f" route={route}"
    if detail:
        msg += f" {detail}"
    LOG.info(
        msg,
        extra={
            "event": "flow.phase",
            "phase": phase,
            "domain": domain,
            "flow": f"{domain}.{phase}",
            "workflow_id": workflow_id,
            "route": route,
            "tracking_id": tracking_id or tracking_id_var.get() or "",
        },
    )


@contextmanager
def outbound_call(
    *,
    domain: str,
    service: str,
    method: str,
    url: str,
    capability: str = "",
) -> Iterator[dict[str, Any]]:
    """Log call.start / call.end around an outbound HTTP/MCP invocation."""
    target = _safe_target(url)
    meta: dict[str, Any] = {"status": "", "ok": True}
    start = time.perf_counter()
    LOG.info(
        "call.start domain=%s callee=%s method=%s target=%s",
        domain,
        service,
        method,
        target,
        extra={
            "event": "call.start",
            "domain": domain,
            "flow": f"{domain}.call",
            "target": target,
            "callee": service,
            "capability": capability,
            "method": method,
        },
    )
    try:
        yield meta
    except Exception as exc:
        meta["ok"] = False
        meta["status"] = type(exc).__name__
        raise
    finally:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        status = str(meta.get("status") or ("ok" if meta.get("ok", True) else "error"))
        LOG.info(
            "call.end domain=%s callee=%s method=%s target=%s status=%s duration_ms=%s",
            domain,
            service,
            method,
            target,
            status,
            elapsed_ms,
            extra={
                "event": "call.end",
                "domain": domain,
                "flow": f"{domain}.call",
                "target": target,
                "callee": service,
                "capability": capability,
                "method": method,
                "status": status,
                "duration_ms": elapsed_ms,
            },
        )
