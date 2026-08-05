"""Build Cliq final release summary card body + optional send."""
from __future__ import annotations

import os
from typing import Any


def build_cliq_final_body(
    *,
    release_name: str,
    stability: dict[str, Any],
    ui_decision: str = "",
    ui_hard_fails: int = 0,
    sheet_url: str = "",
    drive_links: dict[str, str] | None = None,
    grafana_url: str = "",
    owner: str = "",
    action_hint: str | None = None,
) -> str:
    links = drive_links or {}
    band = str(stability.get("band") or "UNKNOWN")
    score = stability.get("stability_score", "?")
    stable = "YES" if stability.get("system_stable") else "NO"
    pillars = stability.get("pillars") or {}
    tech = pillars.get("technical") or {}
    alerts = pillars.get("alerts") or {}
    biz = pillars.get("business") or {}
    firing = alerts.get("firing") or []
    crit = sum(
        1
        for a in firing
        if str(a.get("severity") or a.get("level") or "").lower() in {"critical", "crit"}
    )
    if action_hint is None:
        if band == "UNSTABLE":
            action_hint = "hold/rollback — see Sheet Rollback tags"
        elif band == "AT_RISK":
            action_hint = "watch closely; investigate pillar gaps"
        else:
            action_hint = "none"

    release_id = str(stability.get("release_id") or "")
    temporal_url = (
        links.get("temporal")
        or os.getenv("ASRAX_TEMPORAL_WORKFLOW_URL")
        or (
            f"https://temporal.asrax.in/namespaces/qa-agent/workflows"
            f"?query=WorkflowType%3D%22AsraxReleaseOpsWorkflow%22"
            if release_id
            else ""
        )
    )
    master = links.get("master_pdf") or links.get("final_pdf") or ""
    ui_sum = links.get("ui_summary") or links.get("summary") or ""
    stability_link = links.get("stability") or ""
    dossier = links.get("dossier_pdf") or ""
    drive_folder = links.get("folder") or ""

    lines = [
        f"Asrax {release_name} — FINAL ({band})",
        f"system_stable: {stable} | score: {score}/100",
        f"Soak: {stability.get('soak_minutes', 30)}m | UI suite: {ui_decision or 'n/a'}",
        "",
        f"Pillars: tech {tech.get('score', 0)}/40 | alerts {alerts.get('score', 0)}/30 | business {biz.get('score', 0)}/30",
        f"Critical alerts in window: {crit} | UI hard fails: {ui_hard_fails}",
        "",
        "Links (open these — Cliq webhook cannot attach PDF bytes):",
        f"• Google Sheet (release template): {sheet_url or '(set ASRAX_RELEASE_SHEET_URL)'}",
        f"• Master release PDF (MinIO): {master or '(pending MinIO upload)'}",
        f"• Stability score JSON: {stability_link or '(pending)'}",
        f"• UI suite / Playwright summary: {ui_sum or '(pending)'}",
        f"• Release dossier PDF: {dossier or '(n/a for Asrax pack)'}",
        f"• MinIO pack folder: {drive_folder or '(pending)'}",
        f"• Grafana soak window: {grafana_url or '(set ASRAX_GRAFANA_SOAK_URL)'}",
        f"• Temporal Asrax Release Pipeline: {temporal_url or '(n/a)'}",
        "• Runbook: am-qa-agents/docs/qa-agent/RELEASE_REPORT.md",
        "",
        f"Action: {action_hint}",
        f"Owner: {owner or '(unset)'} | release_id: {release_id}",
    ]
    return "\n".join(lines)


async def send_cliq_final(*, title: str, body: str) -> dict[str, Any]:
    """Send via NotifyClient when available; else direct webhook."""
    if os.getenv("QA_AGENT_SKIP_NOTIFY", "").lower() in {"1", "true", "yes"}:
        return {"skipped": True, "title": title, "body": body}

    try:
        from adapters.specialists import NotifyClient

        client = NotifyClient()
        # Prefer release webhook for final broadcast
        release_hook = (
            os.getenv("QA_AGENT_CLIQ_RELEASE_WEBHOOK_URL")
            or os.getenv("ZOHO_CLIQ_SUMMARY_WEBHOOK_URL")
            or ""
        ).strip()
        if release_hook:
            os.environ["QA_AGENT_CLIQ_WEBHOOK_URL"] = release_hook
        return await client.send_cliq_card(title=title, body=body, meta={"kind": "release_final"})
    except Exception as exc:  # noqa: BLE001 — notify must not crash final run
        return {"ok": False, "error": str(exc), "title": title}
