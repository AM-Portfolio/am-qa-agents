"""Governance activities — SAST, HITL release gate, GitHub checks, learning."""

from __future__ import annotations

from temporalio import activity

from typing import Any

from am_qa_agent.intelligence.security import run_dast_hook, run_sast_hook
from am_qa_agent.adapters.github_checks import upsert_check_run
from am_qa_agent.adapters.growthbook import snapshot_feature_flags
from am_qa_agent.learning import (
    evaluate_learning_offline,
    ingest_feedback_event,
    record_promotion,
)
from am_qa_agent.orchestrator.hitl import await_inline_hitl
from am_qa_agent.observability.metrics import mark_hitl
from am_qa_agent.stores import get_ledger


@activity.defn
async def activity_security_scan(payload: dict[str, Any]) -> dict[str, Any]:
    tracking_id = str(payload["tracking_id"])
    sast = run_sast_hook(
        repo=str(payload.get("repo") or ""),
        head_sha=str(payload.get("head_sha") or ""),
        changed_paths=payload.get("changed_paths"),
        file_snippets=payload.get("file_snippets"),
    )
    dast = run_dast_hook(
        target_url=payload.get("target_url"),
        profile=str(payload.get("dast_profile") or "smoke"),
    )
    flags = await snapshot_feature_flags(environment=payload.get("environment"))
    result = {**sast, "dast": dast, "growthbook": flags}
    get_ledger().upsert_step(tracking_id, "security_scan", result)
    return result


@activity.defn
async def activity_await_release_hitl(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Inline HITL wait (Temporal uses workflow signals instead).

    Registers pending preview (PDF ref) then polls for approve/reject.
    """
    tracking_id = str(payload["tracking_id"])
    get_ledger().upsert_step(
        tracking_id,
        "awaiting_release",
        {
            "pdf_docs_ref": payload.get("pdf_docs_ref"),
            "recommendation": payload.get("recommendation"),
            "gnx_mode": payload.get("gnx_mode"),
            "releasable": payload.get("releasable"),
            "degraded_banner": payload.get("gnx_mode") == "degraded",
        },
    )
    decision = await await_inline_hitl(
        tracking_id,
        pdf_docs_ref=payload.get("pdf_docs_ref"),
        recommendation=payload.get("recommendation"),
        gnx_mode=payload.get("gnx_mode"),
        releasable=bool(payload.get("releasable")),
        workflow_id=payload.get("workflow_id"),
        timeout_seconds=payload.get("timeout_seconds"),
    )
    mark_hitl(str(decision.get("decision") or "unknown"))
    get_ledger().upsert_step(tracking_id, "release_hitl", decision)
    return decision


@activity.defn
async def activity_github_check_run(payload: dict[str, Any]) -> dict[str, Any]:
    tracking_id = str(payload["tracking_id"])
    hitl = payload.get("hitl") or {}
    verification = payload.get("verification") or {}
    decision = hitl.get("decision")
    if decision == "approved":
        conclusion = "success"
    elif decision in {"rejected", "timed_out"}:
        conclusion = "failure"
    elif verification.get("releasable"):
        conclusion = "neutral"
    else:
        conclusion = "failure"
    result = await upsert_check_run(
        repo=str(payload.get("repo") or ""),
        head_sha=str(payload.get("head_sha") or ""),
        conclusion=conclusion,
        title=f"qa-agent {decision or 'complete'}",
        summary=(
            f"tracking_id={tracking_id}\n"
            f"releasable={verification.get('releasable')}\n"
            f"hitl={decision}\n"
            f"pdf={payload.get('pdf_docs_ref')}\n"
        ),
        details_url=payload.get("pdf_docs_ref")
        if str(payload.get("pdf_docs_ref") or "").startswith("http")
        else None,
    )
    get_ledger().upsert_step(tracking_id, "github_check_run", result)
    return result


@activity.defn
async def activity_ingest_hitl_feedback(payload: dict[str, Any]) -> dict[str, Any]:
    tracking_id = str(payload["tracking_id"])
    hitl = payload.get("hitl") or {}
    decision = hitl.get("decision") or "unknown"
    kind = {
        "approved": "approve.release",
        "rejected": "reject.release",
        "timed_out": "hitl_timeout",
        "skipped": "hitl_skipped",
    }.get(str(decision), "release.feedback")
    result = ingest_feedback_event(
        tracking_id=tracking_id,
        kind=kind,
        actor=str(hitl.get("actor") or ""),
        episode_id=payload.get("episode_id"),
        payload=hitl,
    )
    get_ledger().upsert_step(tracking_id, "ingest_feedback", result)
    return result


@activity.defn
async def activity_evaluate_learning(payload: dict[str, Any]) -> dict[str, Any]:
    tracking_id = str(payload["tracking_id"])
    result = evaluate_learning_offline(
        tracking_id=tracking_id,
        episode_payload=payload.get("episode_payload"),
        hitl=payload.get("hitl"),
    )
    get_ledger().upsert_step(tracking_id, "evaluate_learning", result)
    return result


@activity.defn
async def activity_record_promotion(payload: dict[str, Any]) -> dict[str, Any]:
    tracking_id = str(payload.get("tracking_id") or "")
    result = record_promotion(
        candidate_id=str(payload["candidate_id"]),
        human_approved=bool(payload.get("human_approved")),
        offline_eval_passed=payload.get("offline_eval_passed"),
        actor=str(payload.get("actor") or ""),
    )
    if tracking_id:
        get_ledger().upsert_step(tracking_id, "record_promotion", result)
    return result
