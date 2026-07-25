"""Trigger Specs (colocated) SPT load — default 50 iterations per payload API."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from adapters.catalog_ready import _specs_base


def _iterations() -> int:
    return max(1, int(os.getenv("QA_AGENT_SPT_ITERATIONS") or os.getenv("QA_AGENT_API_LOAD_ITERATIONS") or "50"))


def _vus() -> int:
    return max(1, int(os.getenv("QA_AGENT_SPT_VUS") or os.getenv("QA_AGENT_API_LOAD_VUS") or "1"))


async def _poll_run(client: httpx.AsyncClient, base: str, run_id: str) -> dict[str, Any]:
    deadline = asyncio.get_event_loop().time() + float(os.getenv("QA_AGENT_SPT_RUN_TIMEOUT_SEC") or "600")
    last: dict[str, Any] = {}
    while asyncio.get_event_loop().time() < deadline:
        resp = await client.get(f"{base}/api/runs/{run_id}")
        if resp.status_code >= 400:
            return {"ok": False, "error": f"run_status_http_{resp.status_code}", "run_id": run_id}
        last = resp.json() or {}
        status = str(last.get("status") or "").lower()
        if status in {"completed", "failed", "error", "cancelled", "success", "passed"}:
            return {**last, "ok": status in {"completed", "success", "passed"}, "run_id": run_id}
        await asyncio.sleep(3)
    return {**last, "ok": False, "error": "run_timeout", "run_id": run_id}


async def execute_spt_for_service(
    service: str,
    *,
    environment: str | None = None,
    tracking_id: str | None = None,
) -> dict[str, Any]:
    """
    POST /api/runs/execute for ``service`` with iterations=50 (default).

    Specs expands payload APIs from the registered catalog/OpenAPI.
    """
    if os.getenv("QA_AGENT_SKIP_SPT", "").lower() in {"1", "true", "yes"}:
        return {"ok": False, "skipped": True, "reason": "QA_AGENT_SKIP_SPT"}

    base = _specs_base()
    env = environment or os.getenv("DEFAULT_ENVIRONMENT") or "dev"
    iterations = _iterations()
    vus = _vus()
    body = {
        "service": service,
        "environment": env,
        "vus": vus,
        "iterations": iterations,
        "test_type": "k6",
        "preset": os.getenv("QA_AGENT_SPT_PRESET") or None,
    }
    # Drop nulls
    body = {k: v for k, v in body.items() if v is not None}

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        # Enumerate APIs for dossier (per-payload evidence)
        apis_meta: dict[str, Any] = {}
        try:
            apis_resp = await client.get(
                f"{base}/api/catalog/{service}/apis",
                params={"environment": env},
            )
            if apis_resp.status_code < 400:
                apis_meta = apis_resp.json() or {}
        except httpx.HTTPError:
            apis_meta = {}

        api_list = apis_meta.get("apis") or []
        try:
            resp = await client.post(f"{base}/api/runs/execute", json=body)
        except httpx.HTTPError as exc:
            return {
                "ok": False,
                "service": service,
                "error": str(exc),
                "iterations": iterations,
                "vus": vus,
                "api_count": len(api_list),
            }

        if resp.status_code >= 400:
            return {
                "ok": False,
                "service": service,
                "error": f"execute_http_{resp.status_code}",
                "detail": (resp.text or "")[:800],
                "iterations": iterations,
                "vus": vus,
                "api_count": len(api_list),
            }

        started = resp.json() or {}
        run_id = str(started.get("id") or started.get("run_id") or "")
        if not run_id:
            return {
                "ok": False,
                "service": service,
                "error": "missing_run_id",
                "response": started,
                "iterations": iterations,
                "api_count": len(api_list),
            }

        finished = await _poll_run(client, base, run_id)
        return {
            **finished,
            "service": service,
            "environment": env,
            "iterations": iterations,
            "vus": vus,
            "api_count": len(api_list),
            "apis": [
                {"id": a.get("id") or a.get("operationId") or a.get("path"), "method": a.get("method")}
                for a in api_list
                if isinstance(a, dict)
            ][:100],
            "tracking_id": tracking_id,
            "source": "specs_runs_execute",
            "note": f"SPT execute iterations={iterations} (shared across payload APIs)",
        }


async def execute_spt_for_services(
    services: list[str],
    *,
    environment: str | None = None,
    tracking_id: str | None = None,
) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    for name in services:
        if not name:
            continue
        runs.append(
            await execute_spt_for_service(name, environment=environment, tracking_id=tracking_id)
        )
    passed = [r["service"] for r in runs if r.get("ok")]
    failed = [r["service"] for r in runs if not r.get("ok") and not r.get("skipped")]
    return {
        "status": "PASSED" if runs and not failed else ("PARTIAL" if passed else "FAILED"),
        "runs": runs,
        "passed": passed,
        "failed": failed,
        "load": {"vus": _vus(), "iterations": _iterations()},
    }
