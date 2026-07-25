"""Wait until a service appears in Specs SPT catalog (registration race guard)."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

# Services that run UI matrix only — skip SPT catalog wait.
_UI_ONLY = frozenset(
    s.strip()
    for s in (os.getenv("QA_AGENT_UI_ONLY_SERVICES") or "am-modern-ui").split(",")
    if s.strip()
)


def _specs_base() -> str:
    return (
        os.getenv("SPT_PUBLIC_BASE_URL")
        or os.getenv("QA_AGENT_SPECS_BASE_URL")
        or os.getenv("UI_TEST_AGENT_BASE_URL")
        or "http://127.0.0.1:8150"
    ).rstrip("/")


def requires_spt_catalog(service: str | None) -> bool:
    if not service:
        return False
    return service not in _UI_ONLY


async def wait_for_catalog_service(
    service: str,
    *,
    environment: str | None = None,
    timeout_sec: float | None = None,
    poll_sec: float | None = None,
) -> dict[str, Any]:
    """
    Poll GET /api/catalog/registrations until ``service`` is listed.

    Returns ready=True when found; ready=False + reason on timeout.
    """
    timeout_sec = float(
        timeout_sec
        if timeout_sec is not None
        else os.getenv("QA_AGENT_CATALOG_READY_TIMEOUT_SEC") or "180"
    )
    poll_sec = float(
        poll_sec if poll_sec is not None else os.getenv("QA_AGENT_CATALOG_READY_POLL_SEC") or "5"
    )
    base = _specs_base()
    url = f"{base}/api/catalog/registrations"
    deadline = asyncio.get_event_loop().time() + timeout_sec
    attempts = 0
    last_err: str | None = None
    last_ids: list[str] = []

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        while asyncio.get_event_loop().time() < deadline:
            attempts += 1
            try:
                resp = await client.get(url)
                if resp.status_code >= 400:
                    last_err = f"http_{resp.status_code}"
                else:
                    body = resp.json()
                    services = body.get("services") or []
                    last_ids = [
                        str(s.get("id") or s.get("service") or "")
                        for s in services
                        if isinstance(s, dict)
                    ]
                    if service in last_ids:
                        # Optional: apis reachable for env
                        env = environment or os.getenv("DEFAULT_ENVIRONMENT") or "dev"
                        apis_url = f"{base}/api/catalog/{service}/apis"
                        apis_resp = await client.get(apis_url, params={"environment": env})
                        api_count = 0
                        if apis_resp.status_code < 400:
                            api_count = len((apis_resp.json() or {}).get("apis") or [])
                        return {
                            "ready": True,
                            "service": service,
                            "environment": env,
                            "attempts": attempts,
                            "api_count": api_count,
                            "catalog_ids": last_ids,
                            "base_url": base,
                        }
                    last_err = "service_not_in_catalog"
            except httpx.HTTPError as exc:
                last_err = str(exc)
            await asyncio.sleep(poll_sec)

    return {
        "ready": False,
        "service": service,
        "reason": "catalog_not_ready",
        "error": last_err,
        "attempts": attempts,
        "catalog_ids": last_ids,
        "base_url": base,
        "timeout_sec": timeout_sec,
    }
