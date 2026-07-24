"""Await code-intelligence index Job — qa-agent does NOT own sync (§9.0)."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx


async def await_code_intelligence_index(
    *,
    repo: str,
    branch: str,
    head_sha: str,
    gnx_mcp_url: str,
    index_job_url: str = "",
    poll_seconds: float = 5.0,
    timeout_seconds: float = 60.0,
    re_request_on_degraded: bool | None = None,
) -> dict[str, Any]:
    """
    Request index freshness then poll ready.

    Ownership: code-intelligence Job performs sync/analyze.
    qa-agent only triggers + waits (or degrades).
    When degraded and re_request enabled, triggers Job once more then short re-poll.
    """
    if os.getenv("QA_AGENT_SKIP_INDEX_AWAIT", "").lower() in {"1", "true", "yes"}:
        # Explicit skip — not "full" (lie) and not "degraded" (blocks auto-HITL).
        return {
            "gnx_mode": "skipped",
            "sync_owner": "code-intelligence",
            "skipped": True,
            "indexed_repos": [repo.split("/")[-1]],
            "index_commit": head_sha,
            "fallback_level": "L0",
            "mode": "skipped",
            "reason": "QA_AGENT_SKIP_INDEX_AWAIT",
            "note": "Unset skip to run health + GNX MCP; replace with index Job when ready",
        }

    result = await _await_once(
        repo=repo,
        branch=branch,
        head_sha=head_sha,
        gnx_mcp_url=gnx_mcp_url,
        index_job_url=index_job_url,
        poll_seconds=poll_seconds,
        timeout_seconds=timeout_seconds,
        trigger=True,
    )
    do_rereq = (
        re_request_on_degraded
        if re_request_on_degraded is not None
        else os.getenv("QA_AGENT_INDEX_REREQUEST", "true").lower() in {"1", "true", "yes"}
    )
    if result.get("gnx_mode") == "degraded" and do_rereq and index_job_url:
        result["re_request_attempted"] = True
        again = await _await_once(
            repo=repo,
            branch=branch,
            head_sha=head_sha,
            gnx_mcp_url=gnx_mcp_url,
            index_job_url=index_job_url,
            poll_seconds=poll_seconds,
            timeout_seconds=min(30.0, timeout_seconds),
            trigger=True,
        )
        again["re_request_attempted"] = True
        return again
    return result


async def _await_once(
    *,
    repo: str,
    branch: str,
    head_sha: str,
    gnx_mcp_url: str,
    index_job_url: str,
    poll_seconds: float,
    timeout_seconds: float,
    trigger: bool,
) -> dict[str, Any]:
    if trigger and index_job_url:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                await client.post(
                    index_job_url.rstrip("/"),
                    json={
                        "repo": repo,
                        "branch": branch,
                        "head_sha": head_sha,
                        "INDEX_REPOS": repo.split("/")[-1],
                    },
                )
        except httpx.HTTPError as exc:
            return _degraded(repo, head_sha, reason=f"index_job_trigger_failed:{exc}")

    deadline = asyncio.get_event_loop().time() + timeout_seconds
    last_err = "not_probed"
    while asyncio.get_event_loop().time() < deadline:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                health = await client.get(f"{gnx_mcp_url.rstrip('/')}/health")
                if health.status_code < 400:
                    # Enrich with GNX MCP query (real MCP call; replace Job await later)
                    from am_qa_agent.adapters.mcp_fallback import (
                        MODE_FALLBACK_GNX,
                        MODE_LIVE,
                        _mcp_text,
                        gnx_mcp_call,
                    )

                    short = repo.split("/")[-1]
                    gnx = await gnx_mcp_call(
                        tool="query",
                        arguments={
                            "search_query": f"index readiness {short} {head_sha[:12]}",
                            "repo": short,
                            "limit": 4,
                        },
                        base_url=gnx_mcp_url,
                    )
                    out: dict[str, Any] = {
                        "gnx_mode": "full",
                        "sync_owner": "code-intelligence",
                        "indexed_repos": [short],
                        "index_commit": head_sha,
                        "fallback_level": "L0",
                        "health_status": health.status_code,
                        "mode": MODE_LIVE if gnx.get("ok") else MODE_FALLBACK_GNX,
                    }
                    if gnx.get("ok"):
                        out["gnx_mcp_preview"] = _mcp_text(gnx)[:1200]
                        out["via"] = "gnx_mcp"
                    else:
                        out["gnx_mcp_error"] = gnx.get("error") or gnx.get("http_status")
                        out["note"] = "health OK; MCP query failed — still L0 for gate"
                    return out
                last_err = f"health_http_{health.status_code}"
        except httpx.HTTPError as exc:
            last_err = str(exc)
        await asyncio.sleep(poll_seconds)

    return _degraded(repo, head_sha, reason=f"timeout:{last_err}")


def _degraded(repo: str, head_sha: str, *, reason: str) -> dict[str, Any]:
    return {
        "gnx_mode": "degraded",
        "sync_owner": "code-intelligence",
        "indexed_repos": [],
        "index_commit": head_sha,
        "fallback_level": "L1",
        "reason": reason,
        "repo": repo,
        "mode": "fallback_template",
        "note": "Will try GitHub compare in activity; GNX MCP replace when index Job ready",
    }


async def github_compare_fallback(
    *,
    repo: str,
    base_sha: str | None,
    head_sha: str,
    github_token: str | None = None,
) -> dict[str, Any]:
    """L1 — changed file paths via GitHub compare API (no GitNexus)."""
    if not base_sha or not head_sha:
        return {"fallback_level": "L3", "changed_files": [], "reason": "missing_sha"}
    owner_repo = repo if "/" in repo else None
    if not owner_repo:
        return {"fallback_level": "L3", "changed_files": [], "reason": "bad_repo"}
    headers = {"Accept": "application/vnd.github+json"}
    token = github_token or os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"https://api.github.com/repos/{owner_repo}/compare/{base_sha}...{head_sha}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code >= 400:
                return {
                    "fallback_level": "L3",
                    "changed_files": [],
                    "reason": f"github_http_{resp.status_code}",
                }
            data = resp.json()
            files = [f.get("filename") for f in data.get("files") or [] if f.get("filename")]
            return {
                "fallback_level": "L1",
                "changed_files": files,
                "status": data.get("status"),
            }
    except httpx.HTTPError as exc:
        return {"fallback_level": "L3", "changed_files": [], "reason": str(exc)}
