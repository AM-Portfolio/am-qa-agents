"""Start ReleaseReadinessWorkflow on Temporal."""

from __future__ import annotations

import os
from typing import Any

from common.observability.logging_setup import get_logger
from orchestrator.queue import (
    assert_safe_task_queue,
    resolve_namespace,
)

LOG = get_logger("qa.temporal")


async def get_temporal_client():
    from temporalio.client import Client

    from common.observability.tracing import configure_tracing, temporal_interceptors

    configure_tracing(service_name="am-qa-agents")
    host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    namespace = resolve_namespace()
    try:
        from specs.security.credential_store import resolve_temporal_endpoint

        ep = resolve_temporal_endpoint()
        if ep.get("address"):
            host = ep["address"]
        if ep.get("namespace"):
            namespace = ep["namespace"]
    except Exception:  # noqa: BLE001
        pass
    LOG.info(
        "temporal.connect host=%s namespace=%s",
        host,
        namespace,
        extra={
            "event": "temporal.connect",
            "domain": "workflow",
            "flow": "workflow.connect",
            "target": host,
        },
    )
    try:
        client = await Client.connect(
            host,
            namespace=namespace,
            interceptors=temporal_interceptors(),
        )
    except Exception:
        LOG.exception(
            "temporal.connect.failed host=%s namespace=%s",
            host,
            namespace,
            extra={"event": "temporal.connect.error", "domain": "workflow"},
        )
        raise
    return client


async def start_release_readiness(
    *,
    tracking_id: str,
    workflow_id: str,
    args: dict[str, Any],
) -> str:
    from temporalio.common import WorkflowIDReusePolicy

    queue = assert_safe_task_queue()
    namespace = resolve_namespace()
    host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    LOG.info(
        "temporal.start tracking_id=%s workflow_id=%s queue=%s",
        tracking_id,
        workflow_id,
        queue,
        extra={
            "event": "temporal.start",
            "domain": "workflow",
            "flow": "workflow.start",
            "workflow_id": workflow_id,
            "tracking_id": tracking_id,
            "target": f"{host}/{namespace}/{queue}",
        },
    )
    try:
        client = await get_temporal_client()
        handle = await client.start_workflow(
            "ReleaseReadinessWorkflow",
            args,
            id=workflow_id,
            task_queue=queue,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        )
    except Exception:
        LOG.exception(
            "temporal.start.failed tracking_id=%s workflow_id=%s",
            tracking_id,
            workflow_id,
            extra={
                "event": "temporal.start.error",
                "domain": "workflow",
                "workflow_id": workflow_id,
                "tracking_id": tracking_id,
            },
        )
        raise
    LOG.info(
        "temporal.started tracking_id=%s workflow_id=%s",
        tracking_id,
        handle.id,
        extra={
            "event": "temporal.started",
            "domain": "workflow",
            "flow": "workflow.started",
            "workflow_id": handle.id,
            "tracking_id": tracking_id,
        },
    )
    return handle.id


async def start_asrax_release_ops(
    *,
    workflow_id: str,
    args: dict[str, Any],
) -> str:
    """Start AsraxReleaseOpsWorkflow (T0 UI pack → soak → score → publish → Cliq)."""
    from temporalio.common import WorkflowIDReusePolicy

    queue = assert_safe_task_queue()
    namespace = resolve_namespace()
    host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    tracking_id = str(args.get("tracking_id") or "")
    LOG.info(
        "temporal.start AsraxReleaseOpsWorkflow workflow_id=%s queue=%s",
        workflow_id,
        queue,
        extra={
            "event": "temporal.start",
            "domain": "release_ops",
            "flow": "release_ops.start",
            "workflow_id": workflow_id,
            "tracking_id": tracking_id,
            "target": f"{host}/{namespace}/{queue}",
        },
    )
    client = await get_temporal_client()
    handle = await client.start_workflow(
        "AsraxReleaseOpsWorkflow",
        {**args, "workflow_id": workflow_id},
        id=workflow_id,
        task_queue=queue,
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
    )
    LOG.info(
        "temporal.started AsraxReleaseOpsWorkflow workflow_id=%s",
        handle.id,
        extra={
            "event": "temporal.started",
            "domain": "release_ops",
            "flow": "release_ops.started",
            "workflow_id": handle.id,
            "tracking_id": tracking_id,
        },
    )
    return handle.id


async def run_asrax_release_ops_inline(args: dict[str, Any]) -> dict[str, Any]:
    """Local path without Temporal worker (same activity order as the workflow)."""
    from orchestrator.activities.release_ops import (
        activity_release_ops_cliq_final,
        activity_release_ops_complete,
        activity_release_ops_init,
        activity_release_ops_pack_t0,
        activity_release_ops_publish_drive,
        activity_release_ops_publish_sheet,
        activity_release_ops_stability_score,
        activity_release_ops_ui_suite,
        activity_release_ops_wait_deploy_healthy,
    )
    from common.observability.domain_flow import emit_flow_phase

    soak_min = int(args.get("soak_min") or 0)
    emit_flow_phase(phase="release_ops_init", detail="inline")
    init = await activity_release_ops_init(args)
    tracking_id = init["tracking_id"]
    release_id = init["release_id"]
    pack_path = init["pack_path"]

    emit_flow_phase(phase="release_ops_wait_deploy_healthy", tracking_id=tracking_id)
    await activity_release_ops_wait_deploy_healthy(
        {
            "tracking_id": tracking_id,
            "pack_path": pack_path,
            "target_url": args.get("target_url") or args.get("url"),
            "ui_test_base": args.get("ui_test_base"),
            "qa_base": args.get("qa_base"),
            "fixtures": bool(args.get("fixtures")),
            "skip_wait_healthy": bool(args.get("skip_wait_healthy")),
        }
    )

    emit_flow_phase(phase="release_ops_ui_suite", tracking_id=tracking_id)
    ui = await activity_release_ops_ui_suite(
        {
            "tracking_id": tracking_id,
            "release_id": release_id,
            "pack_path": pack_path,
            "suite": args.get("suite") or "prod_ui_full",
            "target_url": args.get("target_url") or args.get("url"),
            "login_mode": args.get("login_mode") or "credentials",
            "portfolio_id": args.get("portfolio_id"),
            "skip_ui": bool(args.get("skip_ui")),
        }
    )

    emit_flow_phase(phase="release_ops_pack_t0", tracking_id=tracking_id)
    pack_t0 = await activity_release_ops_pack_t0(
        {
            "tracking_id": tracking_id,
            "release_id": release_id,
            "pack_path": pack_path,
            "skip_sheet": bool(args.get("skip_sheet")),
            "sheet_id": args.get("sheet_id"),
        }
    )

    if soak_min > 0 and not args.get("skip_soak"):
        import asyncio

        emit_flow_phase(phase="release_ops_soak", tracking_id=tracking_id, detail=f"minutes={soak_min}")
        await asyncio.sleep(soak_min * 60)

    emit_flow_phase(phase="release_ops_stability_score", tracking_id=tracking_id)
    stability = await activity_release_ops_stability_score(
        {
            "tracking_id": tracking_id,
            "release_id": release_id,
            "pack_path": pack_path,
            "soak_min": soak_min,
            "fixtures": bool(args.get("fixtures")),
            "allow_unavailable_stable": bool(args.get("allow_unavailable_stable")),
        }
    )

    emit_flow_phase(phase="release_ops_publish_sheet", tracking_id=tracking_id)
    sheet = await activity_release_ops_publish_sheet(
        {
            "tracking_id": tracking_id,
            "stability": stability,
            "skip_sheet": bool(args.get("skip_sheet")),
            "sheet_id": args.get("sheet_id"),
        }
    )

    emit_flow_phase(phase="release_ops_publish_drive", tracking_id=tracking_id)
    drive = await activity_release_ops_publish_drive(
        {
            "tracking_id": tracking_id,
            "release_id": release_id,
            "pack_path": pack_path,
            "skip_drive": bool(args.get("skip_drive")),
        }
    )

    emit_flow_phase(phase="release_ops_cliq_final", tracking_id=tracking_id)
    cliq = await activity_release_ops_cliq_final(
        {
            "tracking_id": tracking_id,
            "release_id": release_id,
            "release_name": args.get("release_name") or release_id,
            "pack_path": pack_path,
            "stability": stability,
            "drive": drive,
            "ui": ui,
            "skip_cliq": bool(args.get("skip_cliq")),
        }
    )

    emit_flow_phase(phase="release_ops_complete", tracking_id=tracking_id)
    complete = await activity_release_ops_complete(
        {
            "tracking_id": tracking_id,
            "release_id": release_id,
            "pack_path": pack_path,
            "stability": stability,
        }
    )
    return {
        "tracking_id": tracking_id,
        "release_id": release_id,
        "pack_path": pack_path,
        "ui": ui,
        "pack_t0": pack_t0,
        "stability": stability,
        "sheet": sheet,
        "drive": drive,
        "cliq": {k: v for k, v in cliq.items() if k != "body"},
        "complete": complete,
        "system_stable": bool(stability.get("system_stable")),
        "mode": "inline",
    }


async def signal_release_hitl(
    *,
    workflow_id: str,
    signal_name: str,
    payload: dict[str, Any] | None = None,
) -> None:
    LOG.info(
        "temporal.signal workflow_id=%s signal=%s",
        workflow_id,
        signal_name,
        extra={
            "event": "temporal.signal",
            "domain": "governance",
            "flow": "governance.signal",
            "workflow_id": workflow_id,
            "phase": signal_name,
        },
    )
    try:
        client = await get_temporal_client()
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal(signal_name, payload or {})
    except Exception:
        LOG.exception(
            "temporal.signal.failed workflow_id=%s signal=%s",
            workflow_id,
            signal_name,
            extra={
                "event": "temporal.signal.error",
                "domain": "governance",
                "workflow_id": workflow_id,
            },
        )
        raise


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
    from orchestrator.activities import (
        activity_analyze_release,
        activity_await_index,
        activity_await_release_hitl,
        activity_build_test_matrix,
        activity_classify,
        activity_collect_comparisons,
        activity_dev_handoff_ticket,
        activity_evaluate_learning,
        activity_ensure_catalog_ready,
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
    from stores import get_ledger
    from common.observability.domain_flow import emit_flow_phase

    tracking_id = str(args["tracking_id"])
    emit_flow_phase(phase="classify", tracking_id=tracking_id, detail="inline")
    classified = await activity_classify({**args, "trigger": args.get("trigger") or args})
    route = classified["route"]
    emit_flow_phase(phase="classify", tracking_id=tracking_id, route=route, detail="done")
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
        catalog_ready = await activity_ensure_catalog_ready(
            {
                "tracking_id": tracking_id,
                "service": args.get("service") or load_context.get("service"),
                "environment": args.get("environment") or load_context.get("environment"),
            }
        )
        smoke = await activity_execute_matrix(
            {
                "tracking_id": tracking_id,
                "classified": classified,
                "load_context": load_context,
                "index": index,
                "matrix": matrix,
                "fin_prep": fin_prep,
                "catalog_ready": catalog_ready,
                "callback_url": args.get("callback_url"),
                "head_sha": classified.get("head_sha"),
                "branch": classified.get("branch"),
                "environment": args.get("environment") or load_context.get("environment"),
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
        from orchestrator.activities import activity_github_check_run

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

    from observability.metrics import mark_run

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


async def start_or_run_service_onboard(
    *,
    service: str,
    environment: str = "dev",
    strict_payloads: bool = False,
    strict_smoke: bool = False,
    allow_llm: bool = True,
    plugin_id: str | None = None,
    use_temporal: bool = True,
    wait: bool = False,
    workflow_id: str | None = None,
) -> dict[str, Any]:
    """Start ServiceOnboardPrepWorkflow or run inline; shared by gateway + Specs API."""
    import asyncio
    import uuid

    from orchestrator.activities.onboard_report import normalize_env

    svc = (service or "").strip()
    if not svc:
        raise ValueError("service required")
    env = normalize_env(environment)
    wf_id = workflow_id or f"service-onboard-{svc}-{env}-{uuid.uuid4().hex[:10]}"
    args = {
        "service": svc,
        "environment": env,
        "strict_payloads": strict_payloads,
        "strict_smoke": strict_smoke,
        "allow_llm": allow_llm,
        "plugin_id": plugin_id,
        "workflow_id": wf_id,
    }
    force_inline = os.getenv("QA_AGENT_FORCE_INLINE", "").lower() in {"1", "true"}
    if use_temporal and not force_inline:
        try:
            started = await start_service_onboard_prep(workflow_id=wf_id, args=args)
            if wait:
                for _ in range(120):
                    polled = await get_service_onboard_result(started)
                    if polled.get("status") == "COMPLETED" and polled.get("result"):
                        return {
                            "workflow_id": started,
                            "mode": "temporal",
                            "status": "COMPLETED",
                            "result": polled["result"],
                        }
                    if polled.get("status") in {
                        "FAILED",
                        "TERMINATED",
                        "CANCELED",
                        "TIMED_OUT",
                    }:
                        return {
                            "workflow_id": started,
                            "mode": "temporal",
                            "status": polled.get("status"),
                            "result": polled.get("result"),
                            "error": polled.get("error"),
                        }
                    await asyncio.sleep(2)
                return {
                    "workflow_id": started,
                    "mode": "temporal",
                    "status": "RUNNING",
                    "hint": "still running; poll GET …/onboard/{workflow_id}",
                }
            return {"workflow_id": started, "mode": "temporal", "status": "STARTED"}
        except Exception as exc:  # noqa: BLE001
            LOG.warning(
                "onboard.temporal_fallback error=%s",
                exc,
                extra={"event": "onboard.temporal_fallback"},
            )
            outcome = await run_service_onboard_prep_inline(args)
            return {
                "workflow_id": wf_id,
                "mode": "inline_fallback",
                "temporal_error": str(exc),
                "status": "COMPLETED",
                "result": outcome,
            }
    outcome = await run_service_onboard_prep_inline(args)
    return {
        "workflow_id": wf_id,
        "mode": "inline",
        "status": "COMPLETED",
        "result": outcome,
    }


async def start_service_onboard_prep(
    *,
    workflow_id: str,
    args: dict[str, Any],
) -> str:
    """Start ServiceOnboardPrepWorkflow on the release task queue."""
    from temporalio.common import WorkflowIDReusePolicy

    from orchestrator.activities.onboard_report import normalize_env

    queue = assert_safe_task_queue()
    namespace = resolve_namespace()
    host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    service = str(args.get("service") or "")
    env = normalize_env(args.get("environment"))
    LOG.info(
        "temporal.start ServiceOnboardPrepWorkflow workflow_id=%s service=%s env=%s queue=%s",
        workflow_id,
        service,
        env,
        queue,
        extra={
            "event": "temporal.start",
            "domain": "onboard",
            "flow": "onboard.start",
            "workflow_id": workflow_id,
            "target": f"{host}/{namespace}/{queue}",
        },
    )
    client = await get_temporal_client()
    handle = await client.start_workflow(
        "ServiceOnboardPrepWorkflow",
        {**args, "service": service, "environment": env, "workflow_id": workflow_id},
        id=workflow_id,
        task_queue=queue,
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
    )
    LOG.info(
        "temporal.started ServiceOnboardPrepWorkflow workflow_id=%s",
        handle.id,
        extra={
            "event": "temporal.started",
            "domain": "onboard",
            "flow": "onboard.started",
            "workflow_id": handle.id,
        },
    )
    return handle.id


async def get_service_onboard_result(workflow_id: str) -> dict[str, Any]:
    """Poll Temporal for onboard workflow status / result."""
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)
    desc = await handle.describe()
    status = str(getattr(desc.status, "name", None) or desc.status or "UNKNOWN")
    out: dict[str, Any] = {
        "workflow_id": workflow_id,
        "status": status,
        "run_id": getattr(desc, "run_id", None) or getattr(desc.execution_info, "run_id", None),
    }
    if status in {"COMPLETED", "FAILED", "TERMINATED", "CANCELED", "TIMED_OUT"}:
        try:
            if status == "COMPLETED":
                out["result"] = await handle.result()
            else:
                out["result"] = None
        except Exception as exc:  # noqa: BLE001
            out["error"] = str(exc)
    return out


async def run_service_onboard_prep_inline(args: dict[str, Any]) -> dict[str, Any]:
    """Local path without Temporal worker (same activity order as the workflow)."""
    from common.observability.domain_flow import emit_flow_phase
    from orchestrator.activities.onboard_prep import (
        activity_onboard_analyze,
        activity_onboard_apis,
        activity_onboard_auth,
        activity_onboard_contract,
        activity_onboard_generate_payloads,
        activity_onboard_import_data_gen,
        activity_onboard_llm_status,
        activity_onboard_openapi_sync,
        activity_onboard_overview,
        activity_onboard_persist_report,
        activity_onboard_prepare_mcp,
        activity_onboard_tools_refresh,
        activity_onboard_tools_smoke,
    )
    from orchestrator.activities.onboard_report import build_report, normalize_env

    service = str(args.get("service") or "").strip()
    env = normalize_env(args.get("environment"))
    wf_id = str(args.get("workflow_id") or f"onboard-inline-{service}-{env}")
    base = {**args, "service": service, "environment": env, "workflow_id": wf_id, "mode": "inline"}
    steps: list[dict[str, Any]] = []
    warnings: list[str] = []
    payload_set_version: int | None = None
    tool_count: int | None = None
    api_count: int | None = None
    llm_rows = 0

    def _stop(step: dict[str, Any]) -> bool:
        return bool(step.get("hard_fail") or (not step.get("ok") and step.get("required")))

    emit_flow_phase(phase="analyze", detail="inline")
    step = await activity_onboard_analyze(base)
    steps.append(step)
    if _stop(step):
        return await _inline_finish(
            service, env, wf_id, steps, warnings, payload_set_version, tool_count, api_count
        )
    target_url = str((step.get("evidence") or {}).get("target_url") or "")

    emit_flow_phase(phase="openapi_sync", detail="inline")
    step = await activity_onboard_openapi_sync({**base, "target_url": target_url})
    steps.append(step)
    if _stop(step):
        return await _inline_finish(
            service, env, wf_id, steps, warnings, payload_set_version, tool_count, api_count
        )

    emit_flow_phase(phase="apis_catalog", detail="inline")
    step = await activity_onboard_apis(base)
    steps.append(step)
    if _stop(step):
        return await _inline_finish(
            service, env, wf_id, steps, warnings, payload_set_version, tool_count, api_count
        )
    api_count = (step.get("evidence") or {}).get("api_count")

    emit_flow_phase(phase="tools_refresh", detail="inline")
    step = await activity_onboard_tools_refresh(base)
    steps.append(step)
    if _stop(step):
        return await _inline_finish(
            service, env, wf_id, steps, warnings, payload_set_version, tool_count, api_count
        )
    tool_count = (step.get("evidence") or {}).get("tool_count")

    emit_flow_phase(phase="contract", detail="inline")
    step = await activity_onboard_contract(base)
    steps.append(step)
    if _stop(step):
        return await _inline_finish(
            service, env, wf_id, steps, warnings, payload_set_version, tool_count, api_count
        )

    emit_flow_phase(phase="auth_try_token", detail="inline")
    step = await activity_onboard_auth(base)
    steps.append(step)
    if _stop(step):
        return await _inline_finish(
            service, env, wf_id, steps, warnings, payload_set_version, tool_count, api_count
        )

    emit_flow_phase(phase="prepare_mcp", detail="inline")
    step = await activity_onboard_prepare_mcp(base)
    steps.append(step)
    if not step.get("ok") or str(step.get("status") or "").startswith("warn"):
        warnings.append(f"prepare_mcp:{step.get('status')}")

    emit_flow_phase(phase="import_data_gen", detail="inline")
    step = await activity_onboard_import_data_gen(base)
    steps.append(step)
    if str(step.get("status") or "").startswith("warn"):
        warnings.append(f"import_data_gen:{step.get('status')}")
    ev_imp = step.get("evidence") or {}
    if ev_imp.get("payload_set_version") is not None:
        payload_set_version = int(ev_imp["payload_set_version"])

    emit_flow_phase(phase="generate_all_payloads", detail="inline")
    step = await activity_onboard_generate_payloads(base)
    steps.append(step)
    ev = step.get("evidence") or {}
    if ev.get("payload_set_version") is not None:
        payload_set_version = int(ev["payload_set_version"])
    llm_rows = int(ev.get("llm_rows") or 0)
    if _stop(step):
        return await _inline_finish(
            service, env, wf_id, steps, warnings, payload_set_version, tool_count, api_count
        )
    if not step.get("ok"):
        warnings.append(f"generate_all_payloads:{step.get('status')}")

    emit_flow_phase(phase="llm_fallback", detail="inline")
    step = await activity_onboard_llm_status({**base, "llm_rows": llm_rows})
    steps.append(step)

    emit_flow_phase(phase="tools_smoke", detail="inline")
    step = await activity_onboard_tools_smoke(base)
    steps.append(step)
    if step.get("hard_fail"):
        return await _inline_finish(
            service, env, wf_id, steps, warnings, payload_set_version, tool_count, api_count
        )
    if step.get("status") in {"billing_dependency", "smoke_soft_failure"}:
        warnings.append(f"tools_smoke:{step.get('status')}")

    emit_flow_phase(phase="overview_report", detail="inline")
    step = await activity_onboard_overview({**base, "warnings": warnings})
    steps.append(step)

    return await _inline_finish(
        service, env, wf_id, steps, warnings, payload_set_version, tool_count, api_count
    )


async def _inline_finish(
    service: str,
    env: str,
    wf_id: str,
    steps: list[dict[str, Any]],
    warnings: list[str],
    payload_set_version: int | None,
    tool_count: int | None,
    api_count: int | None,
) -> dict[str, Any]:
    from orchestrator.activities.onboard_prep import activity_onboard_persist_report
    from orchestrator.activities.onboard_report import build_report

    report = build_report(
        service=service,
        environment=env,
        workflow_id=wf_id,
        steps=steps,
        payload_set_version=payload_set_version,
        tool_count=tool_count,
        api_count=api_count,
        warnings=warnings,
        mode="inline",
    )
    try:
        await activity_onboard_persist_report(
            {"report": report, "service": service, "environment": env}
        )
    except Exception:  # noqa: BLE001
        LOG.warning("onboard.persist_failed service=%s env=%s", service, env)
    return report
