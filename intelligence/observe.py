"""Observability comparison pack — Phase 2 (§14.2) + MCP fallbacks."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import yaml

from adapters.mcp_fallback import (
    MODE_FALLBACK_GNX,
    MODE_FALLBACK_MCP,
    MODE_FALLBACK_TEMPLATE,
    MODE_OBSERVE,
    MODE_SKIPPED,
    _mcp_text,
    a2a_execute,
    gnx_mcp_call,
    tool_agent_base,
)
from adapters.specialists import load_agent_base_url


def _policy() -> dict[str, Any]:
    from pathlib import Path

    cfg = Path(__file__).resolve().parents[1] / "config" / "release-policy.yaml"
    if cfg.is_file():
        with open(cfg, encoding="utf-8") as f:
            return (yaml.safe_load(f) or {}).get("policy") or {}
    return {}


def _windows(test_start: datetime | None = None) -> dict[str, Any]:
    end = test_start or datetime.now(timezone.utc)
    baseline_end = end
    baseline_start = end - timedelta(minutes=30)
    run_end = end + timedelta(minutes=10)
    return {
        "baseline": {"start": baseline_start.isoformat(), "end": baseline_end.isoformat()},
        "run": {"start": end.isoformat(), "end": run_end.isoformat()},
    }


def _synthetic_comparisons(*, services: list[str], deployments: list[str]) -> dict[str, Any]:
    """Deterministic template when live observe + MCP fallbacks fail."""
    endpoints = []
    for svc in services or ["unknown"]:
        endpoints.append(
            {
                "service": svc,
                "route": "GET /health",
                "latency_ms": {
                    "p50": {"b": 10, "r": 12},
                    "p95": {"b": 40, "r": 45},
                    "p99": {"b": 80, "r": 90},
                },
                "error_rate": {"b": 0.0, "r": 0.0},
                "rps": {"b": 5.0, "r": 8.0},
                "delta_flags": [],
                "source": "template",
            }
        )
    resources = []
    for dep in deployments or services or ["app"]:
        resources.append(
            {
                "deployment": dep,
                "cpu": {"avg_pct_limit": {"b": 20, "r": 35}, "max_pct_limit": {"b": 40, "r": 55}},
                "memory": {"avg_pct_limit": {"b": 30, "r": 40}, "max_pct_limit": {"b": 45, "r": 50}},
                "oom_killed": 0,
                "restarts": {"b": 0, "r": 0},
                "source": "template",
            }
        )
    return {
        "window": _windows(),
        "endpoints": endpoints,
        "resources": resources,
        "pods": [],
        "users": {
            "active_approx": {"b": 1, "r": 2},
            "auth_fail_rate": {"b": 0.0, "r": 0.0},
            "user_facing_5xx": {"b": 0, "r": 0},
            "source": "template",
        },
        "infra_extra": {"hpa_events": [], "deploy_revision": {}, "ingress_5xx": {"b": 0, "r": 0}},
        "dashboard_refs": [],
        "unavailable": ["live_grafana"],
        "mode": MODE_FALLBACK_TEMPLATE,
    }


def _grafana_dashboard_refs() -> list[dict[str, Any]]:
    from pathlib import Path

    cfg = Path(__file__).resolve().parents[1] / "config" / "grafana-catalog.yaml"
    if not cfg.is_file():
        return []
    with open(cfg, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    refs = []
    for d in data.get("dashboards") or []:
        refs.append({"id": d.get("id"), "uid": d.get("uid")})
    return refs


async def collect_comparison_pack(
    *,
    services: list[str] | None = None,
    deployments: list[str] | None = None,
    tool_agent_base_url: str | None = None,
    gnx_mcp_url: str | None = None,
    repo: str | None = None,
) -> dict[str, Any]:
    services = services or []
    deployments = deployments or [s.lower().replace(" ", "-") for s in services]
    windows = _windows()
    dash = _grafana_dashboard_refs()

    if os.getenv("QA_AGENT_SKIP_OBSERVE", "").lower() in {"1", "true", "yes"}:
        # Still try MCP fallbacks unless hard-skip template only
        if os.getenv("QA_AGENT_OBSERVE_FORCE_TEMPLATE", "").lower() in {"1", "true", "yes"}:
            pack = _synthetic_comparisons(services=services, deployments=deployments)
            pack["skipped"] = True
            pack["mode"] = MODE_SKIPPED
            pack["dashboard_refs"] = dash
            return pack

    base = tool_agent_base(tool_agent_base_url or load_agent_base_url("tool-agent"))

    # 1) Live observe via tool-agent A2A
    a2a = await a2a_execute(
        capability="observe.metrics.query",
        payload={
            "services": services,
            "deployments": deployments,
            "windows": windows,
            "metrics": [
                "http_latency_p50",
                "http_latency_p95",
                "http_latency_p99",
                "http_error_rate",
                "cpu_pct_limit",
                "memory_pct_limit",
                "pod_restarts",
            ],
        },
        base_url=base,
    )
    if a2a.get("ok") and isinstance(a2a.get("data"), dict):
        data = a2a["data"]
        if data.get("endpoints") or data.get("comparisons") or data.get("resources"):
            out = data.get("comparisons") or data
            out["mode"] = MODE_OBSERVE
            out.setdefault("window", windows)
            out.setdefault("unavailable", [])
            out["dashboard_refs"] = dash
            return out
        # A2A responded but empty metrics — mark as MCP fallback advisory
        pack = _synthetic_comparisons(services=services, deployments=deployments)
        pack["mode"] = MODE_FALLBACK_MCP
        pack["via"] = "tool_agent_a2a"
        pack["a2a_note"] = "empty_metrics_payload"
        pack["a2a_raw_keys"] = list(data.keys())[:20]
        pack["unavailable"] = ["live_grafana_series"]
        pack["dashboard_refs"] = dash
        return pack

    # 2) GitNexus MCP — service/impact context when Grafana observe is unavailable
    short = (repo or "").split("/")[-1] or "am-core-services"
    gnx = await gnx_mcp_call(
        tool="query",
        arguments={
            "search_query": f"observability metrics health {' '.join(services[:5])}",
            "repo": short,
            "limit": 5,
        },
        base_url=gnx_mcp_url,
    )
    if gnx.get("ok"):
        pack = _synthetic_comparisons(services=services, deployments=deployments)
        pack["mode"] = MODE_FALLBACK_GNX
        pack["via"] = "gnx_mcp"
        pack["gnx_preview"] = _mcp_text(gnx)[:1500]
        pack["unavailable"] = ["observe.metrics.query", "live_grafana"]
        pack["a2a_error"] = a2a.get("error") or a2a.get("http_status")
        pack["dashboard_refs"] = dash
        pack["note"] = "Replace fallback_gnx with live Grafana observe when ready"
        return pack

    pack = _synthetic_comparisons(services=services, deployments=deployments)
    pack["unavailable"] = ["observe.metrics.query", "live_grafana", "gnx_mcp"]
    pack["mode"] = MODE_FALLBACK_TEMPLATE
    pack["a2a_error"] = a2a.get("error") or a2a.get("http_status")
    pack["gnx_error"] = gnx.get("error") or gnx.get("http_status")
    pack["dashboard_refs"] = dash
    return pack


def annotate_deltas(pack: dict[str, Any]) -> dict[str, Any]:
    """Add delta_flags from release-policy thresholds."""
    pol = _policy()
    lat = pol.get("latency") or {}
    p95_warn = float(lat.get("p95_max_delta_pct") or 50)
    p95_block = float(lat.get("p95_block_delta_pct") or 200)
    for ep in pack.get("endpoints") or []:
        flags: list[str] = list(ep.get("delta_flags") or [])
        p95 = (ep.get("latency_ms") or {}).get("p95") or {}
        b, r = float(p95.get("b") or 0), float(p95.get("r") or 0)
        if b > 0:
            pct = ((r - b) / b) * 100
            if pct >= p95_block:
                flags.append("p95_block")
            elif pct >= p95_warn:
                flags.append("p95_warn")
        ep["delta_flags"] = flags
    return pack
