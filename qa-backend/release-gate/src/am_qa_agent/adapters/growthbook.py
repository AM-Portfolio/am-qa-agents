"""GrowthBook feature-flag snapshot at test start."""

from __future__ import annotations

import os
from typing import Any

import httpx


async def snapshot_feature_flags(*, environment: str | None = None) -> dict[str, Any]:
    if os.getenv("QA_AGENT_SKIP_GROWTHBOOK", "true").lower() in {"1", "true", "yes"}:
        return {"skipped": True, "flags": {}, "environment": environment}
    api = os.getenv("GROWTHBOOK_API_HOST") or os.getenv("GROWTHBOOK_URL")
    key = os.getenv("GROWTHBOOK_API_KEY") or os.getenv("GROWTHBOOK_CLIENT_KEY")
    if not api or not key:
        return {"skipped": True, "reason": "missing_growthbook_config", "flags": {}}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{api.rstrip('/')}/api/v1/features",
                headers={"Authorization": f"Bearer {key}"},
            )
            if resp.status_code >= 400:
                return {"ok": False, "http_status": resp.status_code, "flags": {}}
            data = resp.json()
            return {
                "ok": True,
                "environment": environment,
                "flags": data if isinstance(data, dict) else {"raw": data},
            }
    except httpx.HTTPError as exc:
        return {"ok": False, "error": str(exc), "flags": {}}
