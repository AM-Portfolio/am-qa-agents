#!/usr/bin/env python3
"""Commit→SPT CI: resolve branch matrix, execute, poll, notify (email + Cliq).

Used by .github/workflows/spt-on-commit.yml. Stdlib only.
"""
from __future__ import annotations

import json
import os
import smtplib
import sys
import time
import urllib.error
import urllib.request
from email.mime.text import MIMEText
from typing import Any


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def resolve_matrix(git_ref: str) -> dict[str, Any]:
    """Branch → dataset_profile / intensity / preset / fail semantics."""
    ref = (git_ref or "").strip()
    # strip refs/heads/
    if ref.startswith("refs/heads/"):
        ref = ref[len("refs/heads/") :]
    lower = ref.lower()

    def smoke(triggered: str) -> dict[str, Any]:
        return {
            "dataset_profile": "working",
            "profile": "debug",
            "preset": "ci-smoke",
            "vus": 1,
            "iterations": 1,
            "triggered_by": triggered,
            "fail_job_on_unexpected": lower in {"develop", "dev"},
            "matrix_label": "working+debug 1x1",
        }

    if lower in {"main", "master"}:
        return {
            "dataset_profile": "full",
            "profile": "load",
            "preset": "ci-load",
            "vus": 10,
            "iterations": 100,
            "triggered_by": "ci-main",
            "fail_job_on_unexpected": True,
            "matrix_label": "full+load ramp+100iters",
        }
    if lower in {"develop", "dev"}:
        m = smoke("ci-develop")
        m["fail_job_on_unexpected"] = True
        return m
    for prefix in ("feature/", "fix/", "hotfix/", "test/"):
        if lower.startswith(prefix) or ref.startswith(prefix):
            return smoke(f"ci-{prefix.rstrip('/')}")
    # Unknown branch: smoke, report-only
    return smoke("ci-branch")


def _http_json(
    method: str,
    url: str,
    *,
    token: str,
    body: dict | None = None,
    timeout: float = 60,
) -> dict[str, Any]:
    data = None
    headers = {
        "Accept": "application/json",
        "User-Agent": "am-spt-on-commit/1.0 (+https://github.com/AM-Portfolio/am-qa-agents)",
        "X-SPT-API-Key": token,
        "Authorization": f"Bearer {token}",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"HTTP {exc.code} {url}: {detail}") from exc


def portal_run_url(run_id: str) -> str:
    base = _env("SPT_PORTAL_BASE_URL", "https://ai-dev.asrax.in")
    return f"{base.rstrip('/')}/#/runs/{run_id}"


def build_report_card(
    *,
    service: str,
    git_ref: str,
    git_sha: str,
    committer_name: str,
    committer_email: str,
    matrix: dict[str, Any],
    run: dict[str, Any],
) -> str:
    rid = str(run.get("id") or "")
    status = str(run.get("status") or "unknown")
    passed = bool(run.get("passed"))
    pass_n = run.get("api_pass_count")
    expected_n = run.get("api_expected_count")
    unexpected_n = run.get("api_unexpected_fail_count")
    fail_n = run.get("api_fail_count")
    lines = [
        f"SPT report — {service}",
        f"Branch: {git_ref}",
        f"SHA: {git_sha[:12] if git_sha else '?'}",
        f"Committer: {committer_name or '?'} <{committer_email or '?'}>",
        f"Dataset profile: {matrix.get('dataset_profile')}",
        f"Intensity: {matrix.get('profile')} ({matrix.get('matrix_label')})",
        f"Pass / Expected / Unexpected fail: {pass_n} / {expected_n} / {unexpected_n}",
        f"(api_fail_count={fail_n})",
        f"Status: {status} ({'passed' if passed else 'failed'})",
        f"Portal: {portal_run_url(rid) if rid else '(no run id)'}",
    ]
    return "\n".join(lines)


def send_email(subject: str, body: str, to_addr: str) -> None:
    host = _env("SPT_SMTP_HOST")
    port = int(_env("SPT_SMTP_PORT", "587") or "587")
    user = _env("SPT_SMTP_USER")
    password = _env("SPT_SMTP_PASSWORD")
    from_addr = _env("SPT_SMTP_FROM") or user
    if not host or not to_addr or not from_addr:
        print("::warning::SMTP not configured or no committer email — skip mail")
        return
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    use_tls = _env("SPT_SMTP_TLS", "1") not in {"0", "false", "no"}
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        if use_tls:
            smtp.starttls()
        if user and password:
            smtp.login(user, password)
        smtp.sendmail(from_addr, [to_addr], msg.as_string())
    print(f"Emailed SPT report to {to_addr}")


def send_cliq(text: str) -> None:
    url = (
        _env("ZOHO_CLIQ_SPT_WEBHOOK_URL")
        or _env("QA_AGENT_CLIQ_WEBHOOK_URL")
        or _env("ZOHO_CLIQ_WEBHOOK_URL")
    )
    if not url:
        print("::warning::No Cliq webhook — skip Cliq notify")
        return
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"Cliq webhook HTTP {resp.status}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        print(f"::warning::Cliq webhook failed HTTP {exc.code}: {detail}")


def cmd_run() -> int:
    service = _env("SERVICE", "am-market-data")
    git_ref = _env("GIT_REF") or _env("GITHUB_REF_NAME") or "unknown"
    git_sha = _env("GIT_SHA") or _env("GITHUB_SHA") or ""
    committer_email = _env("COMMITTER_EMAIL")
    committer_name = _env("COMMITTER_NAME")
    environment = _env("ENVIRONMENT", "dev")
    qa_base = _env("QA_BASE_URL", "https://am-dev.asrax.in/qa").rstrip("/")
    token = _env("SPT_CI_API_KEY") or _env("QA_AGENT_GATEWAY_TOKEN")
    if not token:
        print("::error::Set SPT_CI_API_KEY or QA_AGENT_GATEWAY_TOKEN")
        return 1

    matrix = resolve_matrix(git_ref)
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
        "git_sha": git_sha,
        "git_ref": git_ref,
        "committer_email": committer_email or None,
        "committer_name": committer_name or None,
        "wait": False,
    }
    print("Execute body:")
    print(json.dumps(body, indent=2))

    started = _http_json("POST", f"{qa_base}/api/runs/execute", token=token, body=body)
    run_id = str(started.get("id") or "")
    if not run_id:
        print(f"::error::No run id in execute response: {started}")
        return 1
    print(f"run_id={run_id}")
    print(f"portal={portal_run_url(run_id)}")

    timeout_sec = int(_env("SPT_POLL_TIMEOUT_SEC", "1200") or "1200")
    poll_sec = int(_env("SPT_POLL_SEC", "10") or "10")
    deadline = time.time() + timeout_sec
    run: dict[str, Any] = {}
    while time.time() < deadline:
        run = _http_json("GET", f"{qa_base}/api/runs/{run_id}", token=token, timeout=30)
        status = str(run.get("status") or "").lower()
        print(
            f"poll status={status} unexpected={run.get('api_unexpected_fail_count')} "
            f"pass={run.get('api_pass_count')}"
        )
        if status in {"passed", "failed", "error", "cancelled"}:
            break
        time.sleep(poll_sec)
    else:
        print("::error::SPT poll timed out")
        run = run or {"id": run_id, "status": "timeout", "passed": False}

    card = build_report_card(
        service=service,
        git_ref=git_ref,
        git_sha=git_sha,
        committer_name=committer_name,
        committer_email=committer_email,
        matrix=matrix,
        run=run,
    )
    print("--- report card ---")
    print(card)
    print("--- end ---")

    outcome = "passed" if run.get("passed") else "failed"
    subject = f"[SPT] {service} {git_ref} — {outcome}"
    try:
        send_email(subject, card, committer_email)
    except Exception as exc:  # noqa: BLE001 — best-effort notify
        print(f"::warning::Email failed: {exc}")
    try:
        send_cliq(card)
    except Exception as exc:  # noqa: BLE001
        print(f"::warning::Cliq failed: {exc}")

    unexpected = int(run.get("api_unexpected_fail_count") or 0)
    if matrix.get("fail_job_on_unexpected") and (not run.get("passed") or unexpected > 0):
        print(f"::error::SPT failed for {git_ref} (unexpected={unexpected})")
        return 1
    if not matrix.get("fail_job_on_unexpected") and not run.get("passed"):
        print("::warning::SPT failed but branch is report-only (feature/*)")
    return 0


def cmd_matrix() -> int:
    """Print matrix JSON for a ref (debug / workflow_dispatch checks)."""
    ref = _env("GIT_REF") or (sys.argv[2] if len(sys.argv) > 2 else "")
    print(json.dumps(resolve_matrix(ref), indent=2))
    return 0


def main() -> int:
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "run").strip().lower()
    if cmd == "matrix":
        return cmd_matrix()
    if cmd == "run":
        return cmd_run()
    print(f"usage: {sys.argv[0]} run|matrix", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
