"""Intake activities — classify trigger, LoadContext, index await, fin prep, notify."""

from __future__ import annotations

from temporalio import activity

import os
from typing import Any

from am_qa_agent.adapters import NotifyClient, UiTestClient
from am_qa_agent.adapters.code_intelligence import (
    await_code_intelligence_index,
    github_compare_fallback,
)
from am_qa_agent.adapters.fin_agent import FinAgentClient
from am_qa_agent.intelligence import classify_trigger
from am_qa_agent.intelligence.load_context import (
    load_smoke_defaults,
    resolve_load_profile,
)
from am_qa_agent.stores import get_ledger


@activity.defn
async def activity_classify(payload: dict[str, Any]) -> dict[str, Any]:
    tracking_id = str(payload["tracking_id"])
    result = classify_trigger(payload.get("trigger") or payload)
    ledger = get_ledger()
    ledger.set_route(tracking_id, result.route)
    ledger.upsert_step(
        tracking_id,
        "classify",
        {
            "route": result.route,
            "reason": result.reason,
            "ci_conclusion": result.ci_conclusion,
            "repo": result.repo,
            "branch": result.branch,
            "head_sha": result.head_sha,
        },
    )
    return {
        "route": result.route,
        "reason": result.reason,
        "ci_conclusion": result.ci_conclusion,
        "repo": result.repo,
        "branch": result.branch,
        "head_sha": result.head_sha,
        "base_sha": result.base_sha,
    }


@activity.defn
async def activity_resolve_load_profile(payload: dict[str, Any]) -> dict[str, Any]:
    tracking_id = str(payload["tracking_id"])
    lc = resolve_load_profile(
        tracking_id=tracking_id,
        repo=str(payload.get("repo") or ""),
        branch=str(payload.get("branch") or ""),
        head_sha=str(payload.get("head_sha") or ""),
        base_sha=payload.get("base_sha"),
        environment=payload.get("environment"),
        changed_paths=payload.get("changed_paths"),
        callback_url=payload.get("callback_url"),
        service=payload.get("service"),
    )
    get_ledger().upsert_step(tracking_id, "resolve_load_profile", {"load_context": lc})
    return lc


@activity.defn
async def activity_await_index(payload: dict[str, Any]) -> dict[str, Any]:
    tracking_id = str(payload["tracking_id"])
    routing = payload.get("routing") or {}
    result = await await_code_intelligence_index(
        repo=str(payload.get("repo") or ""),
        branch=str(payload.get("branch") or ""),
        head_sha=str(payload.get("head_sha") or ""),
        gnx_mcp_url=str(routing.get("gnx_mcp_url") or "http://127.0.0.1:4747"),
        index_job_url=str(routing.get("code_intelligence_index_url") or ""),
        timeout_seconds=float(os.getenv("QA_AGENT_INDEX_AWAIT_TIMEOUT", "60")),
    )
    if result.get("gnx_mode") == "degraded":
        compare = await github_compare_fallback(
            repo=str(payload.get("repo") or ""),
            base_sha=payload.get("base_sha"),
            head_sha=str(payload.get("head_sha") or ""),
        )
        result["compare"] = compare
        result["fallback_level"] = compare.get("fallback_level") or result.get("fallback_level")
        if routing.get("block_release_if_gnx_down"):
            result["blocked"] = True
    get_ledger().upsert_step(tracking_id, "await_index", result)
    return result


@activity.defn
async def activity_fin_data_prep(payload: dict[str, Any]) -> dict[str, Any]:
    tracking_id = str(payload["tracking_id"])
    load_context = payload.get("load_context") or {}
    fin = dict(load_context.get("fin") or {})
    fin["environment"] = load_context.get("environment")
    # Degraded → smoke-defaults services
    index = payload.get("index") or {}
    if index.get("gnx_mode") == "degraded":
        smoke = load_smoke_defaults()
        names = smoke.get("fin_services") or []
        existing = {s.get("name"): s for s in fin.get("services") or []}
        fin["services"] = [existing[n] for n in names if n in existing] or fin.get("services")
        fin["scenarios"] = smoke.get("scenarios") or fin.get("scenarios")
    routing = load_context.get("routing") or {}
    client = FinAgentClient(base_url=routing.get("fin_agent_base_url"))
    result = await client.data_prep(
        fin,
        tracking_id=tracking_id,
        tool_agent_base_url=routing.get("tool_agent_base_url"),
        gnx_mcp_url=routing.get("gnx_mcp_url"),
        repo=str((load_context.get("webhook") or {}).get("repo") or ""),
    )
    get_ledger().upsert_step(tracking_id, "fin_data_prep", {"result": result})
    return result


@activity.defn
async def activity_smoke_ui_test(payload: dict[str, Any]) -> dict[str, Any]:
    tracking_id = str(payload["tracking_id"])
    load_context = payload.get("load_context") or {}
    ui = load_context.get("ui") or {}
    index = payload.get("index") or {}
    profile = payload.get("profile") or ui.get("profile")
    target_url = payload.get("target_url") or ui.get("target_url")
    if index.get("gnx_mode") == "degraded" or load_context.get("docs_only"):
        smoke = load_smoke_defaults()
        profile = smoke.get("profile") or profile or "SMOKE"
    target_url = (
        target_url
        or os.getenv("QA_AGENT_SMOKE_TARGET_URL")
        or "http://127.0.0.1:3000"
    )
    profile = profile or os.getenv("QA_AGENT_SMOKE_PROFILE") or "SMOKE"
    base = (load_context.get("routing") or {}).get("ui_test_agent_base_url")
    client = UiTestClient(base_url=base)
    result = await client.run_smoke(
        target_url=str(target_url),
        profile=str(profile),
        commit_sha=str(payload.get("head_sha") or ""),
        branch=str(payload.get("branch") or ""),
        callback_url=payload.get("callback_url")
        or (load_context.get("github") or {}).get("callback_url"),
    )
    get_ledger().upsert_step(tracking_id, "smoke_ui_test", {"result": result})
    return result


@activity.defn
async def activity_notify(payload: dict[str, Any]) -> dict[str, Any]:
    tracking_id = str(payload["tracking_id"])
    route = str(payload.get("route") or "")
    gnx = payload.get("gnx_mode") or ""
    title = f"[qa-agent] {route} — {payload.get('repo')}@{str(payload.get('head_sha') or '')[:7]}"
    body = (
        f"tracking_id={tracking_id}\n"
        f"reason={payload.get('reason')}\n"
        f"branch={payload.get('branch')}\n"
        f"env={payload.get('environment')}\n"
        f"gnx_mode={gnx}\n"
        f"matrix={payload.get('matrix_summary')}\n"
        f"smoke={payload.get('smoke_status')}\n"
        f"fin={payload.get('fin_status')}\n"
        f"releasable={payload.get('releasable')}\n"
        f"recommendation={payload.get('recommendation')}\n"
        f"pdf={payload.get('pdf_docs_ref')}\n"
        f"episode={payload.get('episode_id')}\n"
        f"work_item={payload.get('work_item_id')}\n"
        f"hitl={payload.get('hitl_decision')}\n"
        f"sast={payload.get('security_status')}\n"
        f"learning_score={payload.get('learning_score')}\n"
    )
    client = NotifyClient()
    result = await client.send_cliq_card(
        title=title,
        body=body,
        meta={
            "tracking_id": tracking_id,
            "route": route,
            "repo": payload.get("repo"),
            "head_sha": payload.get("head_sha"),
            "gnx_mode": gnx,
        },
    )
    get_ledger().upsert_step(tracking_id, "notify", {"result": result})
    return result
