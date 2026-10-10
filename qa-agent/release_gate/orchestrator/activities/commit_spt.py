"""Commit→SPT activity — execute + poll + notify inside qa-agent pod (loopback Specs)."""

from __future__ import annotations

import asyncio
import os
import smtplib
from email.mime.text import MIMEText
from typing import Any

import httpx
from temporalio import activity

from adapters.catalog_ready import _specs_base
from orchestrator.commit_spt_matrix import resolve_commit_spt_matrix


def _portal_run_url(run_id: str) -> str:
    base = (os.getenv("SPT_PORTAL_BASE_URL") or "https://ai-dev.asrax.in").rstrip("/")
    return f"{base}/#/runs/{run_id}"


def _build_card(
    *,
    service: str,
    git_ref: str,
    git_sha: str,
    committer_name: str,
    committer_email: str,
    matrix: dict[str, Any],
    run: dict[str, Any],
) -> str:
    rid = str(run.get("id") or run.get("run_id") or "")
    status = str(run.get("status") or "unknown")
    passed = bool(run.get("passed") or run.get("ok"))
    return "\n".join(
        [
            f"SPT report — {service}",
            f"Branch: {git_ref}",
            f"SHA: {(git_sha or '?')[:12]}",
            f"Committer: {committer_name or '?'} <{committer_email or '?'}>",
            f"Dataset profile: {matrix.get('dataset_profile')}",
            f"Intensity: {matrix.get('profile')} ({matrix.get('matrix_label')})",
            f"Pass / Expected / Unexpected fail: "
            f"{run.get('api_pass_count')} / {run.get('api_expected_count')} / "
            f"{run.get('api_unexpected_fail_count')}",
            f"Status: {status} ({'passed' if passed else 'failed'})",
            f"Portal: {_portal_run_url(rid) if rid else '(no run id)'}",
        ]
    )


async def _send_cliq(text: str) -> dict[str, Any]:
    url = (
        os.getenv("ZOHO_CLIQ_SPT_WEBHOOK_URL")
        or os.getenv("QA_AGENT_CLIQ_WEBHOOK_URL")
        or os.getenv("ZOHO_CLIQ_WEBHOOK_URL")
        or ""
    ).strip()
    if not url:
        return {"ok": False, "skipped": True, "reason": "no_cliq_webhook"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json={"text": text})
        return {"ok": resp.status_code < 400, "status": resp.status_code}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def _send_email(subject: str, body: str, to_addr: str) -> dict[str, Any]:
    host = (os.getenv("SPT_SMTP_HOST") or "").strip()
    from_addr = (os.getenv("SPT_SMTP_FROM") or os.getenv("SPT_SMTP_USER") or "").strip()
    if not host or not to_addr or not from_addr:
        return {"ok": False, "skipped": True, "reason": "smtp_not_configured"}
    port = int(os.getenv("SPT_SMTP_PORT") or "587")
    user = (os.getenv("SPT_SMTP_USER") or "").strip()
    password = (os.getenv("SPT_SMTP_PASSWORD") or "").strip()
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    try:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            if (os.getenv("SPT_SMTP_TLS") or "1").lower() not in {"0", "false", "no"}:
                smtp.starttls()
            if user and password:
                smtp.login(user, password)
            smtp.sendmail(from_addr, [to_addr], msg.as_string())
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


@activity.defn(name="activity_commit_spt")
async def activity_commit_spt(payload: dict[str, Any]) -> dict[str, Any]:
    """Run branch-matrix SPT on colocated Specs, then email + Cliq (best-effort)."""
    service = str(payload.get("service") or "am-market-data")
    git_ref = str(payload.get("branch") or payload.get("git_ref") or "")
    git_sha = str(payload.get("head_sha") or payload.get("git_sha") or "")
    environment = str(payload.get("environment") or "dev")
    committer_email = str(payload.get("committer_email") or "")
    committer_name = str(payload.get("committer_name") or "")
    tracking_id = str(payload.get("tracking_id") or "")

    matrix = resolve_commit_spt_matrix(git_ref)
    base = _specs_base().rstrip("/")
    body = {
        "service": service,
        "environment": environment,
        "audience": "developer",
        "test_type": "k6",
        "dataset_profile": matrix["dataset_profile"],
        "profile": matrix["profile"],
        "preset": matrix["preset"],
        "vus": matrix["vus"],
        "iterations": matrix["iterations"],
        "triggered_by": matrix["triggered_by"],
        "git_sha": git_sha or None,
        "git_ref": git_ref or None,
        "committer_email": committer_email or None,
        "committer_name": committer_name or None,
        "wait": False,
    }
    body = {k: v for k, v in body.items() if v is not None}

    activity.logger.info(
        "commit_spt.execute service=%s ref=%s dataset=%s preset=%s",
        service,
        git_ref,
        matrix["dataset_profile"],
        matrix["preset"],
    )

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.post(f"{base}/api/runs/execute", json=body)
        if resp.status_code >= 400:
            return {
                "ok": False,
                "error": f"execute_http_{resp.status_code}",
                "detail": (resp.text or "")[:800],
                "matrix": matrix,
                "tracking_id": tracking_id,
            }
        started = resp.json() or {}
        run_id = str(started.get("id") or "")
        if not run_id:
            return {
                "ok": False,
                "error": "missing_run_id",
                "response": started,
                "matrix": matrix,
                "tracking_id": tracking_id,
            }

        deadline = asyncio.get_event_loop().time() + float(
            os.getenv("QA_AGENT_SPT_RUN_TIMEOUT_SEC") or "1800"
        )
        run: dict[str, Any] = {}
        while asyncio.get_event_loop().time() < deadline:
            st = await client.get(f"{base}/api/runs/{run_id}")
            run = st.json() if st.status_code < 400 else {}
            status = str(run.get("status") or "").lower()
            if status in {"passed", "failed", "error", "cancelled", "completed", "success"}:
                break
            await asyncio.sleep(5)
        else:
            run = {**(run or {}), "id": run_id, "status": "timeout", "passed": False}

    passed = bool(run.get("passed")) or str(run.get("status") or "").lower() in {
        "passed",
        "success",
        "completed",
    }
    unexpected = int(run.get("api_unexpected_fail_count") or 0)
    if matrix.get("fail_on_unexpected") and (not passed or unexpected > 0):
        ok = False
    elif not matrix.get("fail_on_unexpected"):
        ok = True  # feature branches: report-only
    else:
        ok = passed

    card = _build_card(
        service=service,
        git_ref=git_ref,
        git_sha=git_sha,
        committer_name=committer_name,
        committer_email=committer_email,
        matrix=matrix,
        run=run,
    )
    outcome = "passed" if passed else "failed"
    subject = f"[SPT] {service} {git_ref} — {outcome}"
    email_out = _send_email(subject, card, committer_email)
    cliq_out = await _send_cliq(card)

    out = {
        "ok": ok,
        "passed": passed,
        "run_id": run_id,
        "status": run.get("status"),
        "dataset_profile": matrix.get("dataset_profile"),
        "matrix": matrix,
        "api_pass_count": run.get("api_pass_count"),
        "api_expected_count": run.get("api_expected_count"),
        "api_unexpected_fail_count": unexpected,
        "portal_url": _portal_run_url(run_id),
        "report": card,
        "notify": {"email": email_out, "cliq": cliq_out},
        "tracking_id": tracking_id,
        "workflow_status": "passed" if ok else "failed",
    }
    if tracking_id:
        try:
            from stores import get_ledger

            get_ledger().upsert_step(tracking_id, "commit_spt", out)
        except Exception as exc:  # noqa: BLE001
            activity.logger.warning("commit_spt.ledger_upsert_failed: %s", exc)
    return out
