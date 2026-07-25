"""ReleaseReadinessWorkflow — Phase 0–4."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from orchestrator.activities import (
        activity_analyze_release,
        activity_await_index,
        activity_build_test_matrix,
        activity_classify,
        activity_collect_comparisons,
        activity_dev_handoff_ticket,
        activity_evaluate_learning,
        activity_execute_matrix,
        activity_fin_data_prep,
        activity_github_check_run,
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
    from orchestrator.hitl import (
        SIGNAL_APPROVE_RELEASE,
        SIGNAL_FEEDBACK,
        SIGNAL_REJECT_RELEASE,
        ReleaseHitlState,
    )
    from stores import get_ledger


@workflow.defn(name="ReleaseReadinessWorkflow")
class ReleaseReadinessWorkflow:
    def __init__(self) -> None:
        self._hitl = ReleaseHitlState()

    @workflow.signal(name=SIGNAL_APPROVE_RELEASE)
    def approve_release(self, payload: dict[str, Any] | None = None) -> None:
        self._hitl.apply_signal(SIGNAL_APPROVE_RELEASE, payload)

    @workflow.signal(name=SIGNAL_REJECT_RELEASE)
    def reject_release(self, payload: dict[str, Any] | None = None) -> None:
        self._hitl.apply_signal(SIGNAL_REJECT_RELEASE, payload)

    @workflow.signal(name=SIGNAL_FEEDBACK)
    def release_feedback(self, payload: dict[str, Any] | None = None) -> None:
        self._hitl.apply_signal(SIGNAL_FEEDBACK, payload)

    @workflow.run
    async def run(self, args: dict[str, Any]) -> dict[str, Any]:
        tracking_id = str(args["tracking_id"])
        retry = RetryPolicy(maximum_attempts=3)
        timeout = timedelta(minutes=15)

        classified = await workflow.execute_activity(
            activity_classify,
            {**args, "trigger": args.get("trigger") or args},
            start_to_close_timeout=timeout,
            retry_policy=retry,
        )

        route = classified["route"]
        load_context: dict[str, Any] = {}
        index: dict[str, Any] = {}
        change_intent: dict[str, Any] = {}
        matrix: dict[str, Any] = {}
        fin_prep: dict[str, Any] = {}
        smoke: dict[str, Any] = {}
        handoff: dict[str, Any] = {}
        comparisons: dict[str, Any] = {}
        verification: dict[str, Any] = {}
        analysis: dict[str, Any] = {}
        publication: dict[str, Any] = {}
        security: dict[str, Any] = {}
        hitl: dict[str, Any] = {}
        episode: dict[str, Any] = {}
        learning: dict[str, Any] = {}
        feedback: dict[str, Any] = {}

        if route == "qa-route":
            load_context = await workflow.execute_activity(
                activity_resolve_load_profile,
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
                },
                start_to_close_timeout=timeout,
                retry_policy=retry,
            )

            index = await workflow.execute_activity(
                activity_await_index,
                {
                    "tracking_id": tracking_id,
                    "repo": classified.get("repo"),
                    "branch": classified.get("branch"),
                    "head_sha": classified.get("head_sha"),
                    "base_sha": classified.get("base_sha"),
                    "routing": load_context.get("routing") or {},
                },
                start_to_close_timeout=timedelta(minutes=12),
                retry_policy=retry,
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
                }

            changed = (index.get("compare") or {}).get("changed_files") or args.get("changed_paths")
            if (index.get("compare") or {}).get("changed_files"):
                load_context = await workflow.execute_activity(
                    activity_resolve_load_profile,
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
                    },
                    start_to_close_timeout=timeout,
                    retry_policy=retry,
                )

            security = await workflow.execute_activity(
                activity_security_scan,
                {
                    "tracking_id": tracking_id,
                    "repo": classified.get("repo"),
                    "head_sha": classified.get("head_sha"),
                    "changed_paths": changed,
                    "file_snippets": args.get("file_snippets"),
                },
                start_to_close_timeout=timeout,
                retry_policy=retry,
            )

            change_intent = await workflow.execute_activity(
                activity_interpret_change_intent,
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
                },
                start_to_close_timeout=timeout,
                retry_policy=retry,
            )

            matrix = await workflow.execute_activity(
                activity_build_test_matrix,
                {
                    "tracking_id": tracking_id,
                    "load_context": load_context,
                    "index": index,
                    "change_intent": change_intent,
                },
                start_to_close_timeout=timeout,
                retry_policy=retry,
            )

            plan = matrix.get("execution_plan") or {}
            if plan.get("scenarios") or plan.get("fin_services"):
                fin = dict(load_context.get("fin") or {})
                if plan.get("scenarios"):
                    fin["scenarios"] = plan["scenarios"]
                if plan.get("fin_services"):
                    existing = {s.get("name"): s for s in fin.get("services") or []}
                    fin["services"] = [
                        existing[n] if n in existing else {"name": n, "base_url": "", "spec_url": ""}
                        for n in plan["fin_services"]
                    ]
                load_context = {**load_context, "fin": fin}
                ui = dict(load_context.get("ui") or {})
                if plan.get("ui_profile"):
                    ui["profile"] = plan["ui_profile"]
                if plan.get("specification"):
                    ui["specification"] = plan["specification"]
                load_context = {**load_context, "ui": ui}

            fin_prep = await workflow.execute_activity(
                activity_fin_data_prep,
                {"tracking_id": tracking_id, "load_context": load_context, "index": index},
                start_to_close_timeout=timeout,
                retry_policy=retry,
            )

            smoke = await workflow.execute_activity(
                activity_execute_matrix,
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
                },
                start_to_close_timeout=timedelta(minutes=20),
                retry_policy=retry,
            )

            comparisons = await workflow.execute_activity(
                activity_collect_comparisons,
                {"tracking_id": tracking_id, "load_context": load_context},
                start_to_close_timeout=timeout,
                retry_policy=retry,
            )

            verification = await workflow.execute_activity(
                activity_post_test_verify,
                {
                    "tracking_id": tracking_id,
                    "smoke": smoke,
                    "matrix_results": smoke,
                    "security": security,
                    "comparisons": comparisons,
                    "gnx_mode": index.get("gnx_mode"),
                    "fin_prep": fin_prep,
                    "open_work_items": args.get("open_work_items") or [],
                },
                start_to_close_timeout=timeout,
                retry_policy=retry,
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

            analysis = await workflow.execute_activity(
                activity_analyze_release,
                {"tracking_id": tracking_id, "bundle": bundle},
                start_to_close_timeout=timeout,
                retry_policy=retry,
            )
            bundle["analysis"] = analysis

            publication = await workflow.execute_activity(
                activity_publish_pdf,
                {"tracking_id": tracking_id, "bundle": bundle},
                start_to_close_timeout=timeout,
                retry_policy=retry,
            )
            bundle["publication"] = publication

            # Phase K — HITL release gate (PDF preview available)
            get_ledger().upsert_step(
                tracking_id,
                "awaiting_release",
                {
                    "pdf_docs_ref": publication.get("pdf_docs_ref"),
                    "recommendation": analysis.get("recommendation"),
                    "gnx_mode": index.get("gnx_mode"),
                    "releasable": verification.get("releasable"),
                    "degraded_banner": index.get("gnx_mode") == "degraded",
                },
            )
            hitl_timeout = timedelta(seconds=int(args.get("hitl_timeout_seconds") or 86400))
            try:
                await workflow.wait_condition(
                    lambda: self._hitl.satisfied(),
                    timeout=hitl_timeout,
                )
                hitl = {
                    "decision": self._hitl.decision,
                    "signal": (
                        SIGNAL_APPROVE_RELEASE
                        if self._hitl.decision == "approved"
                        else SIGNAL_REJECT_RELEASE
                    ),
                    "actor": self._hitl.actor,
                    "notes": self._hitl.notes,
                    "pdf_docs_ref": publication.get("pdf_docs_ref"),
                    "degraded_banner": index.get("gnx_mode") == "degraded",
                }
            except TimeoutError:
                hitl = {
                    "decision": "timed_out",
                    "signal": None,
                    "notes": "HITL SLA exceeded",
                    "pdf_docs_ref": publication.get("pdf_docs_ref"),
                    "degraded_banner": index.get("gnx_mode") == "degraded",
                }
            get_ledger().upsert_step(tracking_id, "release_hitl", hitl)
        else:
            handoff = await workflow.execute_activity(
                activity_dev_handoff_ticket,
                {
                    "tracking_id": tracking_id,
                    **classified,
                    "routing": (args.get("routing") or {}),
                    "impact_summary": args.get("impact_summary"),
                    "failure_summary": args.get("failure_summary"),
                },
                start_to_close_timeout=timeout,
                retry_policy=retry,
            )

        final_status = "completed"
        if route == "qa-route":
            if hitl.get("decision") == "approved":
                final_status = "release_approved"
            elif hitl.get("decision") == "rejected":
                final_status = "release_rejected"
            elif hitl.get("decision") == "timed_out":
                final_status = "hitl_timeout"

        episode = await workflow.execute_activity(
            activity_persist_episode,
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
            },
            start_to_close_timeout=timeout,
            retry_policy=retry,
        )

        if route == "qa-route" and hitl:
            feedback = await workflow.execute_activity(
                activity_ingest_hitl_feedback,
                {
                    "tracking_id": tracking_id,
                    "hitl": hitl,
                    "episode_id": episode.get("episode_id"),
                },
                start_to_close_timeout=timeout,
                retry_policy=retry,
            )
            learning = await workflow.execute_activity(
                activity_evaluate_learning,
                {
                    "tracking_id": tracking_id,
                    "hitl": hitl,
                    "episode_payload": {
                        "route": route,
                        "verification": verification,
                        "matrix": matrix,
                        "change_intent": change_intent,
                    },
                },
                start_to_close_timeout=timeout,
                retry_policy=retry,
            )
            await workflow.execute_activity(
                activity_github_check_run,
                {
                    "tracking_id": tracking_id,
                    "repo": classified.get("repo"),
                    "head_sha": classified.get("head_sha"),
                    "hitl": hitl,
                    "verification": verification,
                    "pdf_docs_ref": publication.get("pdf_docs_ref"),
                },
                start_to_close_timeout=timeout,
                retry_policy=retry,
            )

        smoke_status = str(smoke.get("status") or ("n/a" if route != "qa-route" else "unknown"))
        fin_status = str(fin_prep.get("status") or ("n/a" if route != "qa-route" else "unknown"))
        notify = await workflow.execute_activity(
            activity_notify,
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
            },
            start_to_close_timeout=timeout,
            retry_policy=retry,
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
        }
        get_ledger().complete(tracking_id, final_status)
        get_ledger().upsert_step(tracking_id, "complete", outcome)
        return outcome
