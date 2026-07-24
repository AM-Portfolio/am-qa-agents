"""Direct API smoke + light load against LoadContext.fin services.

Used when fin-agent meta/SPT k6 is missing. Always hits real base_urls
(e.g. https://am-dev.asrax.in/analysis) so SPT/API matrix results are honest.
"""

from __future__ import annotations

import asyncio
import os
import statistics
import time
from typing import Any

import httpx

from am_qa_agent.adapters.mcp_fallback import (
    MODE_FALLBACK_MCP,
    MODE_FALLBACK_TEMPLATE,
    MODE_LIVE,
    a2a_execute,
)

# Prefer actuator (Spring) then generic health
_HEALTH_PATHS = (
    "/actuator/health/readiness",
    "/actuator/health/liveness",
    "/actuator/health",
    "/health",
    "/api/v1/health",
)


def _vus() -> int:
    return max(1, int(os.getenv("QA_AGENT_API_LOAD_VUS") or "5"))


def _iterations() -> int:
    return max(1, int(os.getenv("QA_AGENT_API_LOAD_ITERATIONS") or "8"))


def _timeout() -> float:
    return float(os.getenv("QA_AGENT_API_LOAD_TIMEOUT") or "20")


async def _probe_once(
    client: httpx.AsyncClient,
    url: str,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    try:
        resp = await client.get(url)
        ms = (time.perf_counter() - t0) * 1000
        return {
            "ok": resp.status_code < 500,
            "status_code": resp.status_code,
            "latency_ms": round(ms, 1),
            "error": None,
        }
    except httpx.HTTPError as exc:
        ms = (time.perf_counter() - t0) * 1000
        return {
            "ok": False,
            "status_code": None,
            "latency_ms": round(ms, 1),
            "error": str(exc),
        }


async def discover_health_url(
    client: httpx.AsyncClient,
    base_url: str,
) -> dict[str, Any]:
    """Find first usable health URL under base_url."""
    base = base_url.rstrip("/")
    tried: list[dict[str, Any]] = []
    for path in _HEALTH_PATHS:
        url = f"{base}{path}"
        hit = await _probe_once(client, url)
        tried.append({"url": url, **hit})
        # Prefer UP/200-family; 401 on /health is not useful — keep looking
        if hit.get("ok") and hit.get("status_code") in {200, 204}:
            return {"health_url": url, "probe": hit, "tried": tried}
    # Fall back to best non-5xx if any
    for t in tried:
        if t.get("ok"):
            return {"health_url": t["url"], "probe": t, "tried": tried}
    return {"health_url": None, "probe": None, "tried": tried}


async def prepare_services(
    services: list[Any],
    *,
    tracking_id: str,
    scenarios: list[Any] | None = None,
) -> dict[str, Any]:
    """
    Data-prep: resolve health URLs and do a single live probe per service.
    This replaces fictional fin-agent /discover for LoadContext overlays.
    """
    scenarios = list(scenarios or []) or ["health_smoke", "contract_smoke"]
    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=_timeout(), follow_redirects=True) as client:
        for svc in services:
            if isinstance(svc, dict):
                name = str(svc.get("name") or "unknown")
                base = str(svc.get("base_url") or "").rstrip("/")
                spec = str(svc.get("spec_url") or "")
            else:
                name, base, spec = str(svc), "", ""
            if not base:
                results.append(
                    {
                        "name": name,
                        "ok": False,
                        "error": "missing_base_url",
                        "status": "FAILED",
                    }
                )
                continue
            found = await discover_health_url(client, base)
            spec_hit = None
            if spec:
                spec_hit = await _probe_once(client, spec)
            ok = bool(found.get("health_url"))
            results.append(
                {
                    "name": name,
                    "base_url": base,
                    "spec_url": spec or None,
                    "health_url": found.get("health_url"),
                    "health_probe": found.get("probe"),
                    "spec_probe": spec_hit,
                    "ok": ok,
                    "status": "READY" if ok else "UNREACHABLE",
                    "tried": found.get("tried"),
                }
            )

    ready = [r for r in results if r.get("ok")]
    failed = [r for r in results if not r.get("ok")]
    return {
        "status": "OK" if ready and not failed else ("PARTIAL" if ready else "FAILED"),
        "mode": MODE_LIVE if ready else MODE_FALLBACK_TEMPLATE,
        "tracking_id": tracking_id,
        "scenarios": scenarios,
        "services": results,
        "ready_count": len(ready),
        "failed_count": len(failed),
        "note": "Live URL probe (fin-agent meta/discover not deployed on this fin-agent)",
    }


async def _load_url(
    client: httpx.AsyncClient,
    url: str,
    *,
    vus: int,
    iterations: int,
) -> dict[str, Any]:
    """Fire concurrent GETs and summarize latency / errors."""
    latencies: list[float] = []
    codes: dict[str, int] = {}
    errors = 0
    sem = asyncio.Semaphore(vus)

    async def one() -> None:
        nonlocal errors
        async with sem:
            hit = await _probe_once(client, url)
            latencies.append(float(hit["latency_ms"]))
            key = str(hit.get("status_code") or "err")
            codes[key] = codes.get(key, 0) + 1
            if not hit.get("ok"):
                errors += 1

    await asyncio.gather(*(one() for _ in range(iterations)))
    latencies.sort()
    p50 = latencies[len(latencies) // 2] if latencies else None
    p95 = latencies[max(0, int(len(latencies) * 0.95) - 1)] if latencies else None
    return {
        "url": url,
        "vus": vus,
        "iterations": iterations,
        "ok": errors == 0 and bool(latencies),
        "errors": errors,
        "status_codes": codes,
        "latency_ms": {
            "min": min(latencies) if latencies else None,
            "p50": p50,
            "p95": p95,
            "max": max(latencies) if latencies else None,
            "mean": round(statistics.fmean(latencies), 1) if latencies else None,
        },
    }


async def run_api_scenarios(
    *,
    services: list[Any],
    scenarios: list[Any] | None = None,
    tracking_id: str,
    tool_agent_base_url: str | None = None,
    prefer_spt: bool = True,
) -> dict[str, Any]:
    """
    Always run API tests for scheduled services.

    Order:
      1) optional spt.execute (when tool-agent SPT enabled)
      2) direct HTTP health load + contract probe (always for honesty)
    """
    scenarios = [str(s) for s in (scenarios or [])] or ["health_smoke", "contract_smoke"]
    vus = _vus()
    iterations = _iterations()

    spt: dict[str, Any] | None = None
    if prefer_spt and os.getenv("QA_AGENT_SKIP_SPT", "").lower() not in {"1", "true", "yes"}:
        names = [s.get("name") if isinstance(s, dict) else str(s) for s in services]
        spt = await a2a_execute(
            capability="spt.execute",
            payload={
                "tracking_id": tracking_id,
                "services": names,
                "scenarios": scenarios,
                "vus": vus,
                "iterations": iterations,
                "sandbox": True,
            },
            base_url=tool_agent_base_url,
            read_only=False,
        )

    # Direct load — always; SPT stub alone must not count as pass
    service_runs: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=_timeout(), follow_redirects=True) as client:
        for svc in services:
            if isinstance(svc, dict):
                name = str(svc.get("name") or "unknown")
                base = str(svc.get("base_url") or "").rstrip("/")
                spec = str(svc.get("spec_url") or "")
            else:
                name, base, spec = str(svc), "", ""
            entry: dict[str, Any] = {"name": name, "base_url": base, "scenarios": {}}
            if not base:
                entry["ok"] = False
                entry["error"] = "missing_base_url"
                service_runs.append(entry)
                continue

            found = await discover_health_url(client, base)
            health_url = found.get("health_url")
            if "health_smoke" in scenarios:
                if health_url:
                    entry["scenarios"]["health_smoke"] = await _load_url(
                        client, health_url, vus=vus, iterations=iterations
                    )
                else:
                    entry["scenarios"]["health_smoke"] = {
                        "ok": False,
                        "error": "no_health_endpoint",
                        "tried": found.get("tried"),
                    }

            if "contract_smoke" in scenarios and spec:
                spec_hit = await _probe_once(client, spec)
                # 401 means contract exists but auth-gated — warn, not hard fail for P0 health
                entry["scenarios"]["contract_smoke"] = {
                    "url": spec,
                    "ok": bool(spec_hit.get("ok")) or spec_hit.get("status_code") in {401, 403},
                    "auth_gated": spec_hit.get("status_code") in {401, 403},
                    **spec_hit,
                }
            elif "contract_smoke" in scenarios:
                entry["scenarios"]["contract_smoke"] = {
                    "ok": False,
                    "error": "missing_spec_url",
                }

            health_ok = (entry.get("scenarios") or {}).get("health_smoke", {}).get("ok")
            entry["ok"] = bool(health_ok)
            entry["health_url"] = health_url
            service_runs.append(entry)

    passed = [s for s in service_runs if s.get("ok")]
    failed = [s for s in service_runs if not s.get("ok")]
    mode = MODE_LIVE
    if spt and spt.get("ok"):
        mode = MODE_FALLBACK_MCP  # SPT responded but we still trust direct load

    return {
        "status": "PASSED" if service_runs and not failed else ("PARTIAL" if passed else "FAILED"),
        "mode": mode if passed else MODE_FALLBACK_TEMPLATE,
        "tracking_id": tracking_id,
        "scenarios": scenarios,
        "load": {"vus": vus, "iterations": iterations},
        "services": service_runs,
        "passed": [s["name"] for s in passed],
        "failed": [s["name"] for s in failed],
        "spt": {
            "ok": bool(spt and spt.get("ok")),
            "http_status": (spt or {}).get("http_status"),
            "error": (spt or {}).get("error"),
            "note": "SPT optional; direct HTTP load is source of truth until k6 parity",
        }
        if spt is not None
        else {"skipped": True},
        "note": "Direct API load against LoadContext base_urls (always)",
    }
