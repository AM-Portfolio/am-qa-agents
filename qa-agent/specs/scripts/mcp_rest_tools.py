"""Shared HTTP client + MCP tool helpers for qa Specs Cursor bridge."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlencode

import httpx

DEFAULT_BASE_URL = "https://am-dev.asrax.in/spt-poc"
TIMEOUT_SECONDS = 120.0


def base_url() -> str:
    return os.environ.get("QA_SPECS_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def headers() -> dict[str, str]:
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    api_key = os.environ.get("SPT_API_KEY", "").strip()
    if api_key:
        h["X-SPT-Api-Key"] = api_key
    bearer = os.environ.get("SPT_BEARER_TOKEN", "").strip()
    if bearer:
        h["Authorization"] = f"Bearer {bearer}"
    return h


def format_result(data: Any, *, status_code: int) -> str:
    return json.dumps({"status_code": status_code, "body": data}, indent=2, default=str)


def http_get(path: str, params: dict[str, Any] | None = None) -> str:
    qs = ""
    if params:
        cleaned = {k: v for k, v in params.items() if v is not None and v != ""}
        if cleaned:
            qs = "?" + urlencode(cleaned)
    url = f"{base_url()}{path}{qs}"
    with httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=True) as client:
        resp = client.get(url, headers=headers())
    try:
        body: Any = resp.json()
    except Exception:
        body = resp.text
    if resp.status_code >= 400:
        raise RuntimeError(format_result(body, status_code=resp.status_code))
    return format_result(body, status_code=resp.status_code)


def http_post(path: str, payload: dict[str, Any] | None = None) -> str:
    url = f"{base_url()}{path}"
    with httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=True) as client:
        resp = client.post(url, headers=headers(), json=payload or {})
    try:
        body: Any = resp.json()
    except Exception:
        body = resp.text
    if resp.status_code >= 400:
        raise RuntimeError(format_result(body, status_code=resp.status_code))
    return format_result(body, status_code=resp.status_code)


def spt_health() -> str:
    return http_get("/health")


def spt_ready() -> str:
    return http_get("/ready")


def spt_list_services() -> str:
    return http_get("/api/catalog")


def spt_list_apis(service: str, environment: str | None = None) -> str:
    return http_get(f"/api/catalog/{service}/apis", {"environment": environment})


def spt_resolve_target(service: str, environment: str | None = None) -> str:
    return http_get(f"/api/catalog/{service}/target", {"environment": environment})


def spt_list_profiles(
    service: str | None = None,
    environment: str | None = None,
    audience: str | None = None,
) -> str:
    return http_get(
        "/api/profiles",
        {"service": service, "environment": environment, "audience": audience},
    )


def spt_get_profile(config_id: str) -> str:
    return http_get(f"/api/profiles/{config_id}")


def spt_list_runs(
    limit: int = 10,
    offset: int = 0,
    service: str | None = None,
    config_id: str | None = None,
    status: str | None = None,
) -> str:
    return http_get(
        "/api/runs",
        {
            "limit": limit,
            "offset": offset,
            "service": service,
            "config_id": config_id,
            "status": status,
        },
    )


def spt_get_run(run_id: str) -> str:
    return http_get(f"/api/runs/{run_id}")


def spt_get_run_live(run_id: str) -> str:
    # Live progress is embedded on the run record; GET run is the public surface.
    return http_get(f"/api/runs/{run_id}")


def spt_execute_run(
    config_id: str | None = None,
    audience: str | None = None,
    service: str | None = None,
    vus: int | None = None,
    iterations: int | None = None,
    duration: str | None = None,
    profile: str | None = None,
    triggered_by: str = "cursor-mcp",
    wait: bool = False,
) -> str:
    payload: dict[str, Any] = {"triggered_by": triggered_by, "wait": wait}
    for key, value in {
        "config_id": config_id,
        "audience": audience,
        "service": service,
        "vus": vus,
        "iterations": iterations,
        "duration": duration,
        "profile": profile,
    }.items():
        if value is not None and value != "":
            payload[key] = value
    return http_post("/api/runs/execute", payload)


def spt_stop_run(run_id: str) -> str:
    return http_post(f"/api/runs/{run_id}/stop", {})


def spt_list_traces(run_id: str, limit: int = 50, offset: int = 0) -> str:
    return http_get(f"/api/runs/{run_id}/traces", {"limit": limit, "offset": offset})


def spt_compare_runs(run_a: str, run_b: str) -> str:
    return http_get("/api/runs/compare", {"run_a": run_a, "run_b": run_b})
