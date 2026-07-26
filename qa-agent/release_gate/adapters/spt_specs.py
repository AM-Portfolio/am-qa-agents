"""Trigger Specs (colocated) SPT load — default 50 iterations per payload API.

Release-readiness uses ``test_type=mixed`` so one run records:
- real am-analysis (catalog) API calls via k6
- one Playwright profile (AUTH_FLOW_MAIN) as UI entries in the same run id
"""

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


def _ui_profile() -> str:
    return (os.getenv("QA_AGENT_UI_PROFILE") or "AUTH_FLOW_MAIN").strip() or "AUTH_FLOW_MAIN"


def _include_ui() -> bool:
    return (os.getenv("QA_AGENT_SPT_INCLUDE_UI") or "true").lower() in {"1", "true", "yes"}


async def _poll_run(client: httpx.AsyncClient, base: str, run_id: str) -> dict[str, Any]:
    deadline = asyncio.get_event_loop().time() + float(os.getenv("QA_AGENT_SPT_RUN_TIMEOUT_SEC") or "1800")
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
    ui_profile: str | None = None,
    ui_target_url: str | None = None,
    test_type: str | None = None,
) -> dict[str, Any]:
    """
    POST /api/runs/execute for ``service`` with iterations=50 (default).

    Specs expands payload APIs from the registered catalog/OpenAPI.
    Default ``mixed`` so the same run id shows analysis APIs + Playwright steps.
    """
    if os.getenv("QA_AGENT_SKIP_SPT", "").lower() in {"1", "true", "yes"}:
        return {"ok": False, "skipped": True, "reason": "QA_AGENT_SKIP_SPT"}

    base = _specs_base()
    env = environment or os.getenv("DEFAULT_ENVIRONMENT") or "dev"
    iterations = _iterations()
    vus = _vus()
    include_ui = _include_ui() and (test_type or "mixed") != "k6"
    resolved_type = (test_type or ("mixed" if include_ui else "k6")).lower()
    profile = (ui_profile or _ui_profile()).strip() or "AUTH_FLOW_MAIN"

    body: dict[str, Any] = {
        "service": service,
        "environment": env,
        "audience": "ci",
        "vus": vus,
        "iterations": iterations,
        "test_type": resolved_type,
        "preset": os.getenv("QA_AGENT_SPT_PRESET") or None,
        "triggered_by": "qa-agent-release",
    }
    if resolved_type in {"mixed", "playwright"}:
        body["ui_profile"] = profile
        body["login_mode"] = "demo"
        body["design_review_enabled"] = False
        if ui_target_url:
            body["ui_target_url"] = ui_target_url
    # Drop nulls
    body = {k: v for k, v in body.items() if v is not None}

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        from common.observability.domain_flow import outbound_call

        # Enumerate APIs for dossier (per-payload evidence)
        apis_meta: dict[str, Any] = {}
        try:
            resp_url = f"{base}/api/catalog/{service}/apis"
            with outbound_call(
                domain="testing",
                service="specs-spt",
                method="GET",
                url=resp_url,
                capability=service,
            ) as meta:
                apis_resp = await client.get(
                    resp_url,
                    params={"environment": env},
                )
                meta["status"] = str(apis_resp.status_code)
                meta["ok"] = apis_resp.status_code < 400
            if apis_resp.status_code < 400:
                apis_meta = apis_resp.json() or {}
        except httpx.HTTPError:
            apis_meta = {}

        api_list = apis_meta.get("apis") or []
        exec_url = f"{base}/api/runs/execute"
        try:
            with outbound_call(
                domain="testing",
                service="specs-spt",
                method="POST",
                url=exec_url,
                capability=service,
            ) as meta:
                resp = await client.post(exec_url, json=body)
                meta["status"] = str(resp.status_code)
                meta["ok"] = resp.status_code < 400
        except httpx.HTTPError as exc:
            return {
                "ok": False,
                "service": service,
                "error": str(exc),
                "iterations": iterations,
                "vus": vus,
                "api_count": len(api_list),
                "test_type": resolved_type,
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
                "test_type": resolved_type,
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
                "test_type": resolved_type,
            }

        finished = await _poll_run(client, base, run_id)
        api_count = int(finished.get("api_count") or 0)
        # Guard: empty service binding used to "pass" with zero calls
        if finished.get("ok") and resolved_type != "playwright" and api_count == 0 and not api_list:
            finished = {
                **finished,
                "ok": False,
                "error": finished.get("error") or "no_catalog_apis",
            }
        elif finished.get("ok") and resolved_type != "playwright" and api_count == 0:
            finished = {
                **finished,
                "ok": False,
                "error": finished.get("error") or "zero_apis_executed",
            }

        return {
            **finished,
            "service": service,
            "environment": env,
            "iterations": iterations,
            "vus": vus,
            "api_count": api_count or len(api_list),
            "apis": [
                {"id": a.get("id") or a.get("operationId") or a.get("path"), "method": a.get("method")}
                for a in api_list
                if isinstance(a, dict)
            ][:100],
            "tracking_id": tracking_id,
            "source": "specs_runs_execute",
            "test_type": resolved_type,
            "ui_profile": profile if resolved_type in {"mixed", "playwright"} else None,
            "ui_target_url": ui_target_url,
            "ui_test_id": finished.get("ui_test_id"),
            "note": (
                f"SPT {resolved_type} iterations={iterations}"
                + (f" ui_profile={profile}" if resolved_type in {"mixed", "playwright"} else "")
            ),
        }


async def execute_spt_for_services(
    services: list[str],
    *,
    environment: str | None = None,
    tracking_id: str | None = None,
    ui_profile: str | None = None,
    ui_target_url: str | None = None,
    test_type: str | None = None,
) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    for name in services:
        if not name:
            continue
        runs.append(
            await execute_spt_for_service(
                name,
                environment=environment,
                tracking_id=tracking_id,
                ui_profile=ui_profile,
                ui_target_url=ui_target_url,
                test_type=test_type,
            )
        )
    passed = [r["service"] for r in runs if r.get("ok")]
    failed = [r["service"] for r in runs if not r.get("ok") and not r.get("skipped")]
    return {
        "status": "PASSED" if runs and not failed else ("PARTIAL" if passed else "FAILED"),
        "runs": runs,
        "passed": passed,
        "failed": failed,
        "load": {"vus": _vus(), "iterations": _iterations()},
        "test_type": (runs[0].get("test_type") if runs else None),
        "ui_profile": (runs[0].get("ui_profile") if runs else None),
    }
