"""Start ReleaseReadinessWorkflow on Temporal."""

from __future__ import annotations

import os
from typing import Any

from am_qa_agent.orchestrator.queue import (
    assert_safe_task_queue,
    resolve_namespace,
    resolve_task_queue,
)


async def get_temporal_client():
    from temporalio.client import Client

    host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    namespace = resolve_namespace()
    return await Client.connect(host, namespace=namespace)


async def start_release_readiness(
    *,
    tracking_id: str,
    workflow_id: str,
    args: dict[str, Any],
) -> str:
    from temporalio.common import WorkflowIDReusePolicy

    client = await get_temporal_client()
    handle = await client.start_workflow(
        "ReleaseReadinessWorkflow",
        args,
        id=workflow_id,
        task_queue=assert_safe_task_queue(),
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
    )
    return handle.id


async def signal_release_hitl(
    *,
    workflow_id: str,
    signal_name: str,
    payload: dict[str, Any] | None = None,
) -> None:
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)
    await handle.signal(signal_name, payload or {})


def _apply_matrix_plan(load_context: dict, matrix: dict) -> dict:
    plan = matrix.get("execution_plan") or {}
    if not (plan.get("scenarios") or plan.get("fin_services") or plan.get("ui_profile")):
        return load_context
    fin = dict(load_context.get("fin") or {})
    if plan.get("scenarios"):
        fin["scenarios"] = plan["scenarios"]
    if plan.get("fin_services"):
        existing = {s.get("name"): s for s in fin.get("services") or []}
        fin["services"] = [
            existing[n] if n in existing else {"name": n, "base_url": "", "spec_url": ""}
            for n in plan["fin_services"]
        ]
    ui = dict(load_context.get("ui") or {})
    if plan.get("ui_profile"):
        ui["profile"] = plan["ui_profile"]
    if plan.get("specification"):
        ui["specification"] = plan["specification"]
    return {**load_context, "fin": fin, "ui": ui}


async def run_release_readiness_inline(args: dict[str, Any]) -> dict[str, Any]:
    """Local/dev path without Temporal worker (activities only)."""
    from am_qa_agent.orchestrator.activities import (
        activity_analyze_release,
        activity_await_index,
        activity_await_release_hitl,
        activity_build_test_matrix,
        activity_classify,
        activity_collect_comparisons,
        activity_dev_handoff_ticket,
        activity_evaluate_learning,
        activity_execute_matrix,
        activity_fin_data_prep,
        activity_ingest_hitl_feedback,
        activity_interpret_change_intent,
        activity_notify,
        activity_persist_episode,
        activity_post_test_verify,
        activity_publish_pdf,
        activity_resolve_load_profile,
        activity_security_scan,
        build_evidence_bundle,
    )
    from am_qa_agent.stores import get_ledger

    tracking_id = str(args["tracking_id"])
    classified = await activity_classify({**args, "trigger": args.get("trigger") or args})
    route = classified["route"]
    load_context: dict = {}
    index: dict = {}
    change_intent: dict = {}
    matrix: dict = {}
    fin_prep: dict = {}
    smoke: dict = {}
    handoff: dict = {}
    comparisons: dict = {}
    verification: dict = {}
    analysis: dict = {}
    publication: dict = {}
    security: dict = {}
    hitl: dict = {}
    episode: dict = {}
    feedback: dict = {}
    learning: dict = {}

    if route == "qa-route":
        load_context = await activity_resolve_load_profile(
            {
                "tracking_id": tracking_id,
                "repo": classified.get("repo"),
                "branch": classified.get("branch"),
                "head_sha": classified.get("head_sha"),
                "base_sha": classified.get("base_sha"),
                "environment": args.get("environment"),
                "changed_paths": args.get("changed_paths"),
                "callback_url": args.get("callback_url"),
                "service": args.get("service"),
            }
        )
        index = await activity_await_index(
            {
                "tracking_id": tracking_id,
                "repo": classified.get("repo"),
                "branch": classified.get("branch"),
                "head_sha": classified.get("head_sha"),
                "base_sha": classified.get("base_sha"),
                "routing": load_context.get("routing") or {},
            }
        )
        if index.get("blocked"):
            get_ledger().complete(tracking_id, "blocked_gnx_down")
            return {
                "tracking_id": tracking_id,
                "route": route,
                "classify": classified,
                "load_context": load_context,
                "index": index,
                "status": "blocked_gnx_down",
                "mode": "inline",
            }
        changed = (index.get("compare") or {}).get("changed_files") or args.get("changed_paths")
        if (index.get("compare") or {}).get("changed_files"):
            load_context = await activity_resolve_load_profile(
                {
                    "tracking_id": tracking_id,
                    "repo": classified.get("repo"),
                    "branch": classified.get("branch"),
                    "head_sha": classified.get("head_sha"),
                    "base_sha": classified.get("base_sha"),
                    "environment": args.get("environment") or load_context.get("environment"),
                    "changed_paths": (index.get("compare") or {}).get("changed_files"),
                    "callback_url": args.get("callback_url"),
                    "service": args.get("service"),
                }
            )

        security = await activity_security_scan(
            {
                "tracking_id": tracking_id,
                "repo": classified.get("repo"),
                "head_sha": classified.get("head_sha"),
                "changed_paths": changed,
                "file_snippets": args.get("file_snippets"),
            }
        )
        change_intent = await activity_interpret_change_intent(
            {
                "tracking_id": tracking_id,
                "load_context": load_context,
                "index": index,
                "pr_title": args.get("pr_title"),
                "pr_body": args.get("pr_body"),
                "commit_messages": args.get("commit_messages"),
                "work_item_ref": args.get("work_item_ref"),
                "work_item_title": args.get("work_item_title"),
                "work_item_body": args.get("work_item_body"),
            }
        )
        matrix = await activity_build_test_matrix(
            {
                "tracking_id": tracking_id,
                "load_context": load_context,
                "index": index,
                "change_intent": change_intent,
            }
        )
        load_context = _apply_matrix_plan(load_context, matrix)
        fin_prep = await activity_fin_data_prep(
            {"tracking_id": tracking_id, "load_context": load_context, "index": index}
        )
        smoke = await activity_execute_matrix(
            {
                "tracking_id": tracking_id,
                "classified": classified,
                "load_context": load_context,
                "index": index,
                "matrix": matrix,
                "fin_prep": fin_prep,
                "callback_url": args.get("callback_url"),
                "head_sha": classified.get("head_sha"),
                "branch": classified.get("branch"),
            }
        )
        comparisons = await activity_collect_comparisons(
            {"tracking_id": tracking_id, "load_context": load_context}
        )
        verification = await activity_post_test_verify(
            {
                "tracking_id": tracking_id,
                "smoke": smoke,
                "matrix_results": smoke,
                "security": security,
                "comparisons": comparisons,
                "gnx_mode": index.get("gnx_mode"),
                "fin_prep": fin_prep,
                "open_work_items": args.get("open_work_items") or [],
            }
        )
        bundle = build_evidence_bundle(
            tracking_id=tracking_id,
            classified=classified,
            load_context=load_context,
            index=index,
            fin_prep=fin_prep,
            smoke=smoke,
            comparisons=comparisons,
            verification=verification,
            change_intent=change_intent,
            matrix=matrix,
        )
        bundle["security"] = security
        analysis = await activity_analyze_release(
            {"tracking_id": tracking_id, "bundle": bundle}
        )
        bundle["analysis"] = analysis
        publication = await activity_publish_pdf(
            {"tracking_id": tracking_id, "bundle": bundle}
        )
        bundle["publication"] = publication

        hitl = await activity_await_release_hitl(
            {
                "tracking_id": tracking_id,
                "pdf_docs_ref": publication.get("pdf_docs_ref"),
                "recommendation": analysis.get("recommendation"),
                "gnx_mode": index.get("gnx_mode"),
                "releasable": verification.get("releasable"),
                "workflow_id": args.get("workflow_id"),
                "timeout_seconds": args.get("hitl_timeout_seconds"),
            }
        )
    else:
        handoff = await activity_dev_handoff_ticket(
            {
                "tracking_id": tracking_id,
                **classified,
                "routing": args.get("routing") or {},
                "impact_summary": args.get("impact_summary"),
                "failure_summary": args.get("failure_summary"),
            }
        )

    final_status = "completed"
    if route == "qa-route":
        if hitl.get("decision") == "approved":
            final_status = "release_approved"
        elif hitl.get("decision") == "rejected":
            final_status = "release_rejected"
        elif hitl.get("decision") == "timed_out":
            final_status = "hitl_timeout"
        elif hitl.get("decision") == "skipped":
            final_status = "completed"

    episode = await activity_persist_episode(
        {
            "tracking_id": tracking_id,
            "route": route,
            "classified": classified,
            "matrix": matrix,
            "change_intent": change_intent,
            "verification": verification,
            "publication": publication,
            "handoff": handoff,
            "hitl": hitl,
            "security": security,
            "status": final_status,
            "outcome": final_status,
        }
    )

    if route == "qa-route" and hitl:
        feedback = await activity_ingest_hitl_feedback(
            {
                "tracking_id": tracking_id,
                "hitl": hitl,
                "episode_id": episode.get("episode_id"),
            }
        )
        learning = await activity_evaluate_learning(
            {
                "tracking_id": tracking_id,
                "hitl": hitl,
                "episode_payload": {
                    "route": route,
                    "verification": verification,
                    "matrix": matrix,
                    "change_intent": change_intent,
                },
            }
        )
        from am_qa_agent.orchestrator.activities import activity_github_check_run

        await activity_github_check_run(
            {
                "tracking_id": tracking_id,
                "repo": classified.get("repo"),
                "head_sha": classified.get("head_sha"),
                "hitl": hitl,
                "verification": verification,
                "pdf_docs_ref": publication.get("pdf_docs_ref"),
            }
        )

    from am_qa_agent.observability.metrics import mark_run

    mark_run(route=route, status=final_status, gnx_mode=index.get("gnx_mode"))

    smoke_status = str(smoke.get("status") or ("n/a" if route != "qa-route" else "unknown"))
    fin_status = str(fin_prep.get("status") or ("n/a" if route != "qa-route" else "unknown"))
    notify = await activity_notify(
        {
            "tracking_id": tracking_id,
            "route": route,
            "reason": classified.get("reason"),
            "repo": classified.get("repo"),
            "branch": classified.get("branch"),
            "head_sha": classified.get("head_sha"),
            "environment": load_context.get("environment"),
            "gnx_mode": index.get("gnx_mode"),
            "matrix_summary": (matrix.get("summary") or {}),
            "smoke_status": smoke_status,
            "fin_status": fin_status,
            "releasable": verification.get("releasable"),
            "recommendation": analysis.get("recommendation"),
            "pdf_docs_ref": publication.get("pdf_docs_ref"),
            "episode_id": episode.get("episode_id"),
            "work_item_id": handoff.get("work_item_id"),
            "hitl_decision": hitl.get("decision"),
            "security_status": security.get("status"),
            "learning_score": (learning or {}).get("score"),
        }
    )
    outcome = {
        "tracking_id": tracking_id,
        "route": route,
        "classify": classified,
        "load_context": load_context,
        "index": index,
        "security": security,
        "change_intent": change_intent,
        "matrix": matrix,
        "fin_prep": fin_prep,
        "smoke": smoke,
        "comparisons": comparisons,
        "verification": verification,
        "analysis": analysis,
        "publication": publication,
        "hitl": hitl,
        "handoff": handoff,
        "episode": episode,
        "feedback": feedback,
        "learning": learning,
        "notify": notify,
        "status": final_status,
        "mode": "inline",
    }
    get_ledger().complete(tracking_id, final_status)
    get_ledger().upsert_step(tracking_id, "complete", outcome)
    return outcome
