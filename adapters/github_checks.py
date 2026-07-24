"""GitHub check-run updater — attach release dossier link."""

from __future__ import annotations

import os
from typing import Any

import httpx


async def upsert_check_run(
    *,
    repo: str,
    head_sha: str,
    name: str = "qa-agent / release-readiness",
    conclusion: str | None = None,
    title: str,
    summary: str,
    details_url: str | None = None,
) -> dict[str, Any]:
    """
    Create or update a check run. Requires GITHUB_TOKEN with checks:write.
    conclusion: success | failure | neutral | cancelled | timed_out | action_required
    """
    if os.getenv("QA_AGENT_SKIP_GITHUB_CHECKS", "").lower() in {"1", "true", "yes"}:
        return {"skipped": True, "name": name, "head_sha": head_sha, "conclusion": conclusion}

    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token or "/" not in repo:
        return {"skipped": True, "reason": "missing_token_or_repo", "name": name}

    status = "completed" if conclusion else "in_progress"
    payload: dict[str, Any] = {
        "name": name,
        "head_sha": head_sha,
        "status": status,
        "output": {"title": title, "summary": summary},
    }
    if conclusion:
        payload["conclusion"] = conclusion
    if details_url:
        payload["details_url"] = details_url

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"https://api.github.com/repos/{repo}/check-runs"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "http_status": resp.status_code,
                    "data": data,
                    "name": name,
                }
            return {
                "ok": True,
                "check_run_id": data.get("id") if isinstance(data, dict) else None,
                "html_url": data.get("html_url") if isinstance(data, dict) else None,
                "conclusion": conclusion,
            }
    except httpx.HTTPError as exc:
        return {"ok": False, "error": str(exc), "name": name}
