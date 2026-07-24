"""Release evidence analysis — Phase 2 (§14.5). LLM gated; template fallback."""

from __future__ import annotations

import os
from typing import Any


def analyze_release_evidence(bundle: dict[str, Any]) -> dict[str, Any]:
    """
    Synthesize ReleaseEvidenceBundle into narrative fields.

    When QA_AGENT_LLM_ENABLED is false, use deterministic template (no LLM call).
    """
    enabled = os.getenv("QA_AGENT_LLM_ENABLED", "").lower() in {"1", "true", "yes"}
    verification = bundle.get("verification") or {}
    comparisons = bundle.get("comparisons") or {}
    change = bundle.get("change") or {}
    tests = bundle.get("tests") or {}
    gnx = bundle.get("gnx_mode") or "unknown"

    endpoints = comparisons.get("endpoints") or []
    resources = comparisons.get("resources") or []
    blockers = verification.get("blockers") or []
    warnings = verification.get("warnings") or []

    if verification.get("releasable"):
        recommendation = "proceed" if not warnings else "proceed_with_warnings"
    else:
        recommendation = "hold"

    # Template narrative (always available)
    repo = (change.get("repos") or ["unknown"])[0] if isinstance(change.get("repos"), list) else change.get("repo", "unknown")
    exec_summary = (
        f"Release readiness for {repo} (gnx={gnx}): "
        f"{'RELEASABLE' if verification.get('releasable') else 'NOT RELEASABLE'}. "
        f"Blockers={len(blockers)}, warnings={len(warnings)}, "
        f"endpoints_compared={len(endpoints)}, deployments={len(resources)}."
    )
    api = tests.get("api_results") or {}
    ui = tests.get("ui_results") or {}
    code_impact = (
        f"UI status={ui.get('status') or 'n/a'} (mode={ui.get('mode') or 'n/a'}); "
        f"API status={api.get('status') or 'n/a'} (mode={api.get('mode') or 'n/a'}) "
        f"passed={api.get('passed') or []} failed={api.get('failed') or []} "
        f"load={api.get('load') or {}}; "
        f"fin_prep={'yes' if bundle.get('fin_prep') else 'no'}."
    )
    infra_lines: list[str] = []
    for res in resources[:5]:
        # Skip pure template rows when we have live API load
        if (res.get("source") == "template") and (api.get("services")):
            continue
        cpu = ((res.get("cpu") or {}).get("max_pct_limit") or {}).get("r")
        mem = ((res.get("memory") or {}).get("max_pct_limit") or {}).get("r")
        infra_lines.append(
            f"{res.get('deployment')}: cpu_max%={cpu} mem_max%={mem} oom={res.get('oom_killed')}"
        )
    if not infra_lines:
        for svc in api.get("services") or []:
            health = (svc.get("scenarios") or {}).get("health_smoke") or {}
            lat = health.get("latency_ms") if isinstance(health.get("latency_ms"), dict) else {}
            if health:
                infra_lines.append(
                    f"{svc.get('name')} health p50={lat.get('p50')} p95={lat.get('p95')} "
                    f"ok={health.get('ok')}"
                )
    infra_impact = "; ".join(infra_lines) or "No resource series (observe unavailable)."

    risks = list(blockers) + [f"warn:{w}" for w in warnings[:10]]
    feature_narrative = (
        f"Feature health feature_clean={verification.get('feature_clean')} "
        f"infra_clean={verification.get('infra_clean')}. "
        f"{exec_summary}"
    )

    analysis = {
        "executive_summary": exec_summary,
        "feature_narrative": feature_narrative,
        "code_impact": code_impact,
        "infra_impact": infra_impact,
        "risks": risks,
        "recommendation": recommendation,
        "llm_used": False,
        "mode": "fallback_template",
    }

    if enabled:
        from am_qa_agent.intelligence.llm import get_llm_client
        from am_qa_agent.observability.metrics import mark_llm

        client = get_llm_client()
        mark_llm("qa-release-analysis")
        analysis = client.complete_json(
            prompt_name="qa-release-analysis",
            inputs={"bundle_keys": list(bundle.keys()), "recommendation": recommendation},
            fallback=analysis,
        )
        analysis["llm_enabled"] = True

    return analysis
