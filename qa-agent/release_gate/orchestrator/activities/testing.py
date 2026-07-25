"""Testing activities — ChangeIntent, matrix plan/execute, ticket handoff, episodes."""

from __future__ import annotations

from temporalio import activity

import os
import uuid
from typing import Any

from adapters.specialists import UiTestClient, WorkItemClient
from intelligence.change_intent import interpret_change_intent
from intelligence.matrix import matrix_execution_plan, rank_matrix
from stores import get_ledger
from stores.episodes import (
    QaEpisode,
    evaluate_learning,
    get_episode_store,
)


@activity.defn
async def activity_interpret_change_intent(payload: dict[str, Any]) -> dict[str, Any]:
    tracking_id = str(payload["tracking_id"])
    intent = interpret_change_intent(
        load_context=payload.get("load_context") or {},
        index=payload.get("index"),
        pr_title=payload.get("pr_title"),
        pr_body=payload.get("pr_body"),
        commit_messages=payload.get("commit_messages"),
        work_item_ref=payload.get("work_item_ref"),
        work_item_title=payload.get("work_item_title"),
        work_item_body=payload.get("work_item_body"),
    )
    get_ledger().upsert_step(tracking_id, "interpret_change_intent", intent)
    return intent


@activity.defn
async def activity_build_test_matrix(payload: dict[str, Any]) -> dict[str, Any]:
    tracking_id = str(payload["tracking_id"])
    matrix = rank_matrix(
        load_context=payload.get("load_context") or {},
        index=payload.get("index"),
        change_intent=payload.get("change_intent"),
    )
    plan = matrix_execution_plan(matrix, payload.get("load_context") or {})
    out = {**matrix, "execution_plan": plan}
    get_ledger().upsert_step(tracking_id, "build_test_matrix", {"summary": matrix.get("summary"), "plan": plan})
    return out


@activity.defn
async def activity_ensure_catalog_ready(payload: dict[str, Any]) -> dict[str, Any]:
    """Block SPT until service is visible in Specs catalog (register → ready race guard)."""
    from adapters.catalog_ready import requires_spt_catalog, wait_for_catalog_service

    tracking_id = str(payload.get("tracking_id") or "")
    service = payload.get("service")
    environment = payload.get("environment")
    if not requires_spt_catalog(str(service) if service else None):
        out = {
            "ready": True,
            "skipped": True,
            "reason": "ui_only_or_no_service",
            "service": service,
        }
        if tracking_id:
            get_ledger().upsert_step(tracking_id, "ensure_catalog_ready", out)
        return out

    out = await wait_for_catalog_service(str(service), environment=environment)
    if tracking_id:
        get_ledger().upsert_step(tracking_id, "ensure_catalog_ready", out)
    return out


@activity.defn
async def activity_execute_matrix(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Run scheduled matrix layers via specialists.

    API layer: Specs SPT execute (50 iters default) + live HTTP health/contract load.
    UI via ui-test-agent when available. Skips SPT when catalog_ready.ready is false.
    """
    from adapters.api_load import run_api_scenarios
    from adapters.spt_specs import execute_spt_for_services

    tracking_id = str(payload["tracking_id"])
    load_context = payload.get("load_context") or {}
    matrix = payload.get("matrix") or {}
    plan = matrix.get("execution_plan") or matrix_execution_plan(matrix, load_context)
    classified = payload.get("classified") or {}
    index = payload.get("index") or {}
    fin_prep = payload.get("fin_prep") or {}
    catalog_ready = payload.get("catalog_ready") or {}

    ui = load_context.get("ui") or {}
    profile = plan.get("ui_profile") or ui.get("profile") or "SMOKE"
    target_url = (
        ui.get("target_url")
        or __import__("os").getenv("QA_AGENT_SMOKE_TARGET_URL")
        or "http://127.0.0.1:3000"
    )
    base = (load_context.get("routing") or {}).get("ui_test_agent_base_url")
    client = UiTestClient(base_url=base)
    routing = load_context.get("routing") or {}
    ui_result = await client.run_smoke(
        target_url=str(target_url),
        profile=str(profile),
        commit_sha=str(classified.get("head_sha") or payload.get("head_sha") or ""),
        branch=str(classified.get("branch") or payload.get("branch") or ""),
        callback_url=payload.get("callback_url")
        or (load_context.get("github") or {}).get("callback_url"),
        tool_agent_base_url=routing.get("tool_agent_base_url"),
        gnx_mcp_url=routing.get("gnx_mcp_url"),
    )
    ui_result = {
        **ui_result,
        "profile": profile,
        "specification": plan.get("specification"),
        "screenshots": ui_result.get("screenshots")
        or ui_result.get("screenshot_urls")
        or ui_result.get("artifacts")
        or [],
        "reportUrl": ui_result.get("reportUrl") or ui_result.get("report_url"),
        "matrix_item_ids": [
            i["id"] for i in (matrix.get("items") or []) if i.get("layer") == "ui" and i.get("tier") in {"P0", "P1"}
        ],
    }

    # Resolve full service objects (name + base_url + spec_url) from LoadContext
    fin_services_ctx = (load_context.get("fin") or {}).get("services") or []
    plan_names = set(plan.get("fin_services") or [])
    services_for_api = [
        s
        for s in fin_services_ctx
        if isinstance(s, dict) and (not plan_names or s.get("name") in plan_names)
    ] or fin_services_ctx
    scenarios = (
        plan.get("scenarios")
        or (load_context.get("fin") or {}).get("scenarios")
        or ["health_smoke", "contract_smoke"]
    )

    spt_run: dict[str, Any] = {"skipped": True, "reason": "no_api_services"}
    service_names = [
        str(s.get("name"))
        for s in services_for_api
        if isinstance(s, dict) and s.get("name")
    ]
    if catalog_ready.get("ready") is False:
        spt_run = {
            "ok": False,
            "skipped": True,
            "reason": "catalog_not_ready",
            "catalog_ready": catalog_ready,
        }
        api_run = {
            "status": "FAILED",
            "mode": "catalog_not_ready",
            "tracking_id": tracking_id,
            "services": [],
            "passed": [],
            "failed": service_names,
            "load": {},
            "spt": spt_run,
            "note": "SPT/API skipped — catalog registration not ready",
        }
    else:
        if service_names:
            spt_run = await execute_spt_for_services(
                service_names,
                environment=load_context.get("environment") or payload.get("environment"),
                tracking_id=tracking_id,
            )
        api_run = await run_api_scenarios(
            services=services_for_api,
            scenarios=scenarios,
            tracking_id=tracking_id,
            tool_agent_base_url=routing.get("tool_agent_base_url"),
        )
        api_run = {**api_run, "spt_specs": spt_run}
    api_layer = {
        **api_run,
        "fin_prep": fin_prep,
        "spt_specs": spt_run,
        "catalog_ready": catalog_ready,
        "matrix_item_ids": [
            i["id"] for i in (matrix.get("items") or []) if i.get("layer") == "api" and i.get("tier") in {"P0", "P1"}
        ],
    }

    flow_layer = {
        "status": "PLANNED",
        "flows": plan.get("flows") or [],
        "note": "Flow fan-out deferred to specialist catalog SPT; recorded for dossier",
        "matrix_item_ids": [
            i["id"] for i in (matrix.get("items") or []) if i.get("layer") == "flow" and i.get("tier") in {"P0", "P1"}
        ],
    }

    item_results: list[dict[str, Any]] = []
    ui_optional = str(os.getenv("QA_AGENT_UI_OPTIONAL") or "").lower() in {"1", "true", "yes"}
    ui_skipped = bool(ui_result.get("skipped"))
    ui_status = str(ui_result.get("status") or "").lower()
    ui_ok = (not ui_skipped) and ui_status in {
        "completed",
        "done",
        "succeeded",
        "success",
        "passed",
    }
    if ui_skipped and ui_optional:
        ui_ok = True

    live_ok = str(api_run.get("status") or "").upper() in {"PASSED", "OK"}
    spt_status = str(spt_run.get("status") or "").upper() if isinstance(spt_run, dict) else ""
    spt_skipped = bool(isinstance(spt_run, dict) and spt_run.get("skipped"))
    spt_ok = spt_skipped or spt_status in {"PASSED", "OK"} or (
        isinstance(spt_run, dict) and bool(spt_run.get("ok")) and not spt_run.get("failed")
    )
    if isinstance(spt_run, dict) and spt_run.get("failed"):
        spt_ok = False
    if isinstance(spt_run, dict) and spt_status == "FAILED":
        spt_ok = False
    # API P0 requires both live HTTP and Specs SPT (when SPT ran / was expected)
    api_ok = live_ok and (spt_ok or spt_skipped)

    for item in matrix.get("p0") or []:
        layer = item.get("layer")
        passed = True
        release_blocker = True
        if layer == "ui":
            passed = ui_ok
        elif layer == "api":
            svc = item.get("service")
            live_svc_ok = live_ok
            if svc:
                match = next((s for s in (api_run.get("services") or []) if s.get("name") == svc), None)
                live_svc_ok = bool(match and match.get("ok")) if match is not None else live_ok
            spt_svc_ok = spt_ok
            if svc and isinstance(spt_run, dict) and isinstance(spt_run.get("runs"), list):
                spt_match = next(
                    (r for r in spt_run["runs"] if r.get("service") == svc),
                    None,
                )
                if spt_match is not None:
                    spt_svc_ok = bool(spt_match.get("ok")) or bool(spt_match.get("skipped"))
            passed = live_svc_ok and spt_svc_ok
        elif layer == "flow":
            # Planned-only — do not block release until flow executor exists
            passed = True
            release_blocker = False
        item_results.append(
            {
                "id": item["id"],
                "tier": "P0",
                "layer": layer,
                "passed": passed,
                "release_blocker": release_blocker,
            }
        )

    p0_failed = [r["id"] for r in item_results if r.get("release_blocker") and not r["passed"]]
    layers_failed: list[str] = []
    if not ui_ok:
        layers_failed.append("ui")
    if not api_ok:
        layers_failed.append("api")
    aggregate = "FAILED" if (p0_failed or layers_failed) else "PASSED"

    out = {
        "ui": ui_result,
        "api": api_layer,
        "flow": flow_layer,
        "item_results": item_results,
        "p0_failed": p0_failed,
        "gnx_mode": index.get("gnx_mode"),
        "status": aggregate,
        "skipped": ui_result.get("skipped"),
        "reportUrl": ui_result.get("reportUrl") or ui_result.get("report_url"),
        "layers": {
            "ui_ok": ui_ok,
            "live_ok": live_ok,
            "spt_ok": spt_ok,
            "api_ok": api_ok,
            "failed": layers_failed,
        },
    }
    get_ledger().upsert_step(
        tracking_id,
        "execute_matrix",
        {
            "ui_status": ui_result.get("status"),
            "api_status": api_run.get("status"),
            "api_mode": api_run.get("mode"),
            "api_passed": api_run.get("passed"),
            "api_failed": api_run.get("failed"),
            "api_load": api_run.get("load"),
            "spt_specs_status": spt_run.get("status") if isinstance(spt_run, dict) else None,
            "spt_specs_failed": spt_run.get("failed") if isinstance(spt_run, dict) else None,
            "p0_failed": out["p0_failed"],
            "plan": plan,
        },
    )
    return out


@activity.defn
async def activity_dev_handoff_ticket(payload: dict[str, Any]) -> dict[str, Any]:
    """Ticket-only handoff — no auto-fix (testing policy)."""
    tracking_id = str(payload["tracking_id"])
    repo = payload.get("repo")
    sha = payload.get("head_sha")
    reason = payload.get("reason") or "ci_failed"
    subject = f"[qa-agent] CI failed — {repo}@{str(sha or '')[:7]}"
    description = (
        f"tracking_id: {tracking_id}\n"
        f"repo: {repo}\n"
        f"branch: {payload.get('branch')}\n"
        f"head_sha: {sha}\n"
        f"ci_conclusion: {payload.get('ci_conclusion')}\n"
        f"reason: {reason}\n"
        f"mode: ticket_only (no auto-fix)\n"
        f"gnx_mode: {payload.get('gnx_mode') or 'n/a'}\n"
        f"impact: {payload.get('impact_summary') or {}}\n"
    )
    if payload.get("failure_summary"):
        description += f"\nfailure_summary:\n{payload['failure_summary']}\n"

    routing = payload.get("routing") or {}
    client = WorkItemClient(base_url=routing.get("tool_agent_base_url"))
    result = await client.create(
        subject=subject,
        description=description,
        meta={
            "tracking_id": tracking_id,
            "repo": repo,
            "head_sha": sha,
            "mode": "ticket_only",
            "ci_conclusion": payload.get("ci_conclusion"),
        },
    )
    handoff = {
        "kind": "dev_handoff_ticket",
        "mode": "ticket_only",
        "repo": repo,
        "head_sha": sha,
        "ci_conclusion": payload.get("ci_conclusion"),
        "reason": reason,
        **result,
    }
    get_ledger().upsert_step(tracking_id, "dev_handoff", handoff)
    return handoff


@activity.defn
async def activity_persist_episode(payload: dict[str, Any]) -> dict[str, Any]:
    tracking_id = str(payload["tracking_id"])
    learning = evaluate_learning(payload)
    episode_id = f"ep-{uuid.uuid4().hex[:12]}"
    ep = QaEpisode(
        episode_id=episode_id,
        tracking_id=tracking_id,
        repo=(payload.get("classified") or {}).get("repo") or payload.get("repo"),
        head_sha=(payload.get("classified") or {}).get("head_sha") or payload.get("head_sha"),
        route=payload.get("route"),
        outcome=payload.get("outcome") or payload.get("status") or "completed",
        payload={
            "matrix_summary": (payload.get("matrix") or {}).get("summary"),
            "verification": payload.get("verification"),
            "change_intent_id": (payload.get("change_intent") or {}).get("change_intent_id"),
            "releasable": (payload.get("verification") or {}).get("releasable"),
            "pdf_docs_ref": (payload.get("publication") or {}).get("pdf_docs_ref"),
            "handoff": payload.get("handoff"),
        },
        learning_score=learning["score"],
    )
    get_episode_store().persist(ep)
    out = {
        "episode_id": episode_id,
        "learning": learning,
        "tracking_id": tracking_id,
    }
    get_ledger().upsert_step(tracking_id, "persist_episode", out)
    return out


# Keep name for older imports
@activity.defn
async def activity_dev_handoff_stub(payload: dict[str, Any]) -> dict[str, Any]:
    return await activity_dev_handoff_ticket(payload)
