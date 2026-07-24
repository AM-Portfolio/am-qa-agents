"""fin-agent data prep + live LoadContext URL probe."""

from __future__ import annotations

import os
from typing import Any

import httpx

from adapters.api_load import prepare_services
from adapters.mcp_fallback import (
    MODE_FALLBACK_GNX,
    MODE_FALLBACK_MCP,
    MODE_FALLBACK_TEMPLATE,
    MODE_LIVE,
    MODE_SKIPPED,
    _mcp_text,
    a2a_execute,
    gnx_mcp_call,
)


class FinAgentClient:
    def __init__(self, base_url: str | None = None, client: httpx.AsyncClient | None = None) -> None:
        self.base_url = (
            base_url or os.getenv("FIN_AGENT_BASE_URL") or "http://127.0.0.1:8100"
        ).rstrip("/")
        self._client = client

    async def data_prep(
        self,
        load_fin: dict[str, Any],
        *,
        tracking_id: str,
        tool_agent_base_url: str | None = None,
        gnx_mcp_url: str | None = None,
        repo: str | None = None,
    ) -> dict[str, Any]:
        """
        Prepare API test targets from LoadContext.fin.

        Prefer live URL probe against service base_urls (always works for am-analysis).
        Optional fin-agent meta routes when present; MCP only as last resort.
        """
        services = load_fin.get("services") or []
        scenarios = load_fin.get("scenarios") or ["health_smoke", "contract_smoke"]
        body = {
            "load": {
                "environment": load_fin.get("environment"),
                "tracking_id": tracking_id,
                "services": services,
                "scenarios": scenarios,
                "impacted_ops": load_fin.get("impacted_ops") or [],
            }
        }

        if os.getenv("QA_AGENT_SKIP_FIN_AGENT", "").lower() in {"1", "true", "yes"}:
            # Still probe live URLs — skip only means skip fin-agent HTTP meta
            live = await prepare_services(services, tracking_id=tracking_id, scenarios=scenarios)
            live["prior"] = {"status": "SKIPPED", "reason": "QA_AGENT_SKIP_FIN_AGENT"}
            live["requested"] = body
            return live

        # 1) Live probe against LoadContext URLs (source of truth for data prep)
        live = await prepare_services(services, tracking_id=tracking_id, scenarios=scenarios)
        if live.get("ready_count", 0) > 0:
            live["requested"] = body
            live["via"] = "direct_url_probe"
            return live

        # 2) Optional fin-agent meta (often absent on deployed fin-agent)
        owns = self._client is None
        http = self._client or httpx.AsyncClient(timeout=60.0)
        try:
            for path in ("/api/v1/meta/services", "/api/v1/meta/config"):
                try:
                    resp = await http.get(f"{self.base_url}{path}")
                    if resp.status_code < 400:
                        return {
                            "status": "OK",
                            "mode": MODE_LIVE,
                            "via": "fin_agent_meta",
                            "data": _safe_json(resp),
                            "requested": body,
                            "probe": live,
                        }
                except httpx.HTTPError:
                    continue
        finally:
            if owns:
                await http.aclose()

        return await self._mcp_fallbacks(
            body=body,
            services=services,
            scenarios=scenarios,
            tracking_id=tracking_id,
            tool_agent_base_url=tool_agent_base_url,
            gnx_mcp_url=gnx_mcp_url,
            repo=repo,
            prior_status=str(live.get("status") or "FAILED"),
            prior_reason="url_probe_failed",
            probe=live,
        )

    async def _mcp_fallbacks(
        self,
        *,
        body: dict[str, Any],
        services: list[Any],
        scenarios: list[Any],
        tracking_id: str,
        tool_agent_base_url: str | None,
        gnx_mcp_url: str | None,
        repo: str | None,
        prior_status: str,
        prior_reason: str,
        probe: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        names = [s.get("name") if isinstance(s, dict) else str(s) for s in services]
        a2a = await a2a_execute(
            capability="spt.test-data.prepare",
            payload={
                "tracking_id": tracking_id,
                "services": names,
                "scenarios": scenarios,
                "service_urls": [
                    {"name": s.get("name"), "base_url": s.get("base_url"), "spec_url": s.get("spec_url")}
                    for s in services
                    if isinstance(s, dict)
                ],
            },
            base_url=tool_agent_base_url,
            read_only=False,
        )
        if a2a.get("ok") and isinstance(a2a.get("data"), dict):
            return {
                "status": "PREPARED_MCP",
                "mode": MODE_FALLBACK_MCP,
                "via": a2a.get("via") or "tool_agent_execute",
                "capability": a2a.get("capability"),
                "data": a2a["data"],
                "services": services,
                "scenarios": scenarios,
                "prior": {"status": prior_status, "reason": prior_reason},
                "probe": probe,
                "requested": body,
                "note": "SPT prepare fallback; prefer live URL probe",
            }

        short = (repo or "").split("/")[-1] or "am-core-services"
        gnx = await gnx_mcp_call(
            tool="query",
            arguments={
                "search_query": f"release readiness data prep services {' '.join(names)}",
                "repo": short,
                "limit": 6,
            },
            base_url=gnx_mcp_url,
        )
        if gnx.get("ok"):
            return {
                "status": "PREPARED_GNX",
                "mode": MODE_FALLBACK_GNX,
                "via": "gnx_mcp",
                "services": services,
                "scenarios": scenarios,
                "gnx_preview": _mcp_text(gnx)[:1500],
                "prior": {"status": prior_status, "reason": prior_reason},
                "probe": probe,
                "a2a": {"ok": a2a.get("ok"), "error": a2a.get("error"), "http_status": a2a.get("http_status")},
                "requested": body,
            }

        return {
            "status": prior_status,
            "mode": MODE_FALLBACK_TEMPLATE if prior_status != "SKIPPED" else MODE_SKIPPED,
            "skipped": prior_status == "SKIPPED",
            "services": services,
            "scenarios": scenarios,
            "prior_reason": prior_reason,
            "probe": probe,
            "a2a": {"ok": a2a.get("ok"), "error": a2a.get("error")},
            "gnx": {"ok": gnx.get("ok"), "error": gnx.get("error")},
            "requested": body,
            "note": "No live health URL and MCP fallbacks failed",
        }


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:  # noqa: BLE001
        return {"text": resp.text[:500]}
