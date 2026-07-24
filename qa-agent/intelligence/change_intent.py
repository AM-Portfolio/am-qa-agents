"""ChangeIntent synthesis — Phase 3 (§10.1). Advisory only; never drives P0 alone."""

from __future__ import annotations

import os
import uuid
from typing import Any


def interpret_change_intent(
    *,
    load_context: dict[str, Any],
    index: dict[str, Any] | None = None,
    pr_title: str | None = None,
    pr_body: str | None = None,
    commit_messages: list[str] | None = None,
    work_item_ref: str | None = None,
    work_item_title: str | None = None,
    work_item_body: str | None = None,
) -> dict[str, Any]:
    """
    Build ChangeIntent from facts + PR/work-item text.

    When QA_AGENT_LLM_ENABLED is false → deterministic template from paths/services.
    When true → same template + llm placeholder (Langfuse wire-up later).
    """
    index = index or {}
    lc = load_context or {}
    webhook = lc.get("webhook") or {}
    fin = lc.get("fin") or {}
    ui = lc.get("ui") or {}
    gnx_mode = str(index.get("gnx_mode") or "full")
    llm_on = os.getenv("QA_AGENT_LLM_ENABLED", "").lower() in {"1", "true", "yes"}

    services = [
        s.get("name") if isinstance(s, dict) else str(s)
        for s in (fin.get("services") or [])
    ]
    services = [s for s in services if s]
    scenarios = list(fin.get("scenarios") or [])
    profile = ui.get("profile") or "SMOKE"
    repo = webhook.get("repo") or ""
    branch = webhook.get("branch") or ""

    title = (pr_title or work_item_title or "").strip()
    body = (pr_body or work_item_body or "").strip()
    commits = commit_messages or []
    text_blob = " ".join([title, body, *commits]).lower()

    flows: list[str] = []
    if "portfolio" in text_blob or "AUTH_FLOW_PORTFOLIO" in str(profile):
        flows.append("portfolio_view")
    if "mover" in text_blob or "market" in text_blob:
        flows.append("market_movers")
    if "auth" in text_blob or "login" in text_blob:
        flows.append("auth_login")
    if not flows and scenarios:
        flows = [str(s) for s in scenarios[:3]]

    risk_hypotheses: list[str] = []
    if len(services) > 1:
        risk_hypotheses.append(f"Multi-service touch: {', '.join(services[:4])}")
    if gnx_mode == "degraded":
        risk_hypotheses.append("GitNexus degraded — impact incomplete; prefer smoke floor")
    if lc.get("docs_only"):
        risk_hypotheses.append("Docs-only path set — minimal matrix expected")

    suggested: list[dict[str, Any]] = []
    if profile:
        suggested.append({"ui_profile": profile})
    if scenarios:
        suggested.append({"fin_scenarios": scenarios})
    if services:
        suggested.append({"services": services, "repo": repo.split("/")[-1] if repo else ""})

    user_goal = title or (commits[0] if commits else f"Release readiness for {repo}@{branch}")
    author_scope = body[:400] if body else "No PR/work-item body; inferred from LoadContext + index"

    confidence = "medium"
    if gnx_mode == "degraded":
        confidence = "low"
    elif llm_on:
        confidence = "medium"

    intent = {
        "change_intent_id": f"ci-{uuid.uuid4().hex[:10]}",
        "user_goal": user_goal,
        "affected_user_flows": flows,
        "author_stated_scope": author_scope,
        "risk_hypotheses": risk_hypotheses,
        "suggested_test_focus": suggested,
        "confidence": confidence,
        "provenance": {
            "llm_model": None,
            "langfuse_trace_id": None,
            "gnx_mode": gnx_mode,
            "work_item_ref": work_item_ref,
            "mode": "template_llm_placeholder" if llm_on else "template",
        },
        "advisory_only": True,
    }
    if llm_on:
        intent["note"] = "QA_AGENT_LLM_ENABLED; wire Langfuse prompt qa-change-intent"
    return intent
