"""HTTP client for am-ui-test-agent (Playwright UI runs)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_TERMINAL = frozenset(
    {
        "COMPLETED",
        "FAILED",
        "GO",
        "GO_WITH_CAVEATS",
        "NO_GO",
    }
)


class UiTestAgentError(RuntimeError):
    pass


def _base() -> str:
    url = (settings.ui_test_agent_url or "").rstrip("/")
    if not url:
        raise UiTestAgentError(
            "SPT_UI_TEST_AGENT_URL is not set — cannot run Playwright via ui-test-agent"
        )
    return url


async def list_profiles() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{_base()}/api/v1/test/profiles")
        r.raise_for_status()
        return r.json()


async def start_profile(
    *,
    profile: str,
    target_url: str,
    login_mode: str | None = None,
    baseline_mode: str | None = None,
    design_review_enabled: bool | None = None,
    portfolio_id: str | None = None,
    branch: str | None = None,
    commit_sha: str | None = None,
) -> str:
    body: dict[str, Any] = {
        "profile": profile,
        "targetUrl": target_url,
    }
    if login_mode:
        body["loginMode"] = login_mode
    if baseline_mode:
        body["baselineMode"] = baseline_mode
    if design_review_enabled is not None:
        body["designReviewEnabled"] = design_review_enabled
    if portfolio_id:
        body["portfolioId"] = portfolio_id
    if branch:
        body["branch"] = branch
    if commit_sha:
        body["commitSha"] = commit_sha
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{_base()}/api/v1/test/run/profile", json=body)
        if r.status_code >= 400:
            raise UiTestAgentError(f"start profile failed: {r.status_code} {r.text[:500]}")
        data = r.json()
    test_id = data.get("testId")
    if not test_id:
        raise UiTestAgentError(f"ui-test-agent did not return testId: {data}")
    return str(test_id)


async def start_suite(
    *,
    suite: str,
    target_url: str,
    login_mode: str | None = None,
    design_review_enabled: bool | None = None,
    portfolio_id: str | None = None,
    branch: str | None = None,
    commit_sha: str | None = None,
    profiles: list[str] | None = None,
) -> str:
    body: dict[str, Any] = {
        "suite": suite,
        "targetUrl": target_url,
    }
    if login_mode:
        body["loginMode"] = login_mode
    if design_review_enabled is not None:
        body["designReviewEnabled"] = design_review_enabled
    if portfolio_id:
        body["portfolioId"] = portfolio_id
    if branch:
        body["branch"] = branch
    if commit_sha:
        body["commitSha"] = commit_sha
    if profiles:
        body["profiles"] = profiles
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{_base()}/api/v1/test/run/suite", json=body)
        if r.status_code >= 400:
            raise UiTestAgentError(f"start suite failed: {r.status_code} {r.text[:500]}")
        data = r.json()
    test_id = data.get("testId")
    if not test_id:
        raise UiTestAgentError(f"ui-test-agent did not return testId: {data}")
    return str(test_id)


async def get_status(test_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{_base()}/api/v1/test/status/{test_id}")
        if r.status_code == 404:
            raise UiTestAgentError(f"unknown testId {test_id}")
        r.raise_for_status()
        return r.json()


async def poll_until_done(
    test_id: str,
    *,
    interval_s: float = 2.0,
    timeout_s: float | None = None,
    on_status: Any = None,
) -> dict[str, Any]:
    """Poll status until terminal. on_status(dict) called each poll."""
    limit = timeout_s if timeout_s is not None else float(settings.max_duration_seconds + 300)
    elapsed = 0.0
    last: dict[str, Any] = {}
    while elapsed < limit:
        last = await get_status(test_id)
        if on_status:
            try:
                on_status(last)
            except Exception:
                logger.debug("on_status callback failed", exc_info=True)
        status = str(last.get("status") or "").upper()
        if status in _TERMINAL:
            return last
        await asyncio.sleep(interval_s)
        elapsed += interval_s
    raise UiTestAgentError(
        f"ui-test-agent timed out after {limit}s (last status={last.get('status')})"
    )


async def fetch_report_json(test_id: str) -> dict[str, Any] | None:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(f"{_base()}/api/v1/test/report/{test_id}/json")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()


async def fetch_report_html(test_id: str) -> bytes | None:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(f"{_base()}/api/v1/test/report/{test_id}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.content


async def fetch_report_pdf(test_id: str) -> bytes | None:
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.get(f"{_base()}/api/v1/test/report/{test_id}/pdf")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.content


async def fetch_trace_zip(test_id: str) -> bytes | None:
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.get(f"{_base()}/api/v1/test/trace/{test_id}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.content


async def fetch_screenshot(test_id: str, filename: str) -> bytes | None:
    """Download a per-step evidence PNG from ui-test-agent."""
    name = str(filename).rsplit("/", 1)[-1].strip()
    if not name or ".." in name or "/" in name or "\\" in name:
        return None
    if not name.lower().endswith(".png"):
        return None
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(f"{_base()}/api/v1/test/screenshot/{test_id}/{name}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.content


def agent_report_html_url(test_id: str) -> str:
    return f"{_base()}/api/v1/test/report/{test_id}"
