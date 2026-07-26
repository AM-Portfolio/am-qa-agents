#!/usr/bin/env python3
"""Stdio MCP bridge: Cursor mcp.json -> qa Specs REST API (/spt-poc).

Native /mcp is not reliably reachable via public ingress today; this bridge
uses the same REST surface the portal uses.
"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts = Path(__file__).resolve().parent
sys.path.insert(0, str(_scripts))

from mcp.server.fastmcp import FastMCP

import mcp_rest_tools as tools

mcp = FastMCP(
    "AM QA Specs",
    instructions=(
        "QA Specs control plane via REST. Prefer spt_health, spt_list_profiles, "
        "spt_list_runs, spt_get_run_live. Mutating tools (execute/stop) need care."
    ),
)


@mcp.tool()
def spt_health() -> str:
    """Check qa Specs health."""
    return tools.spt_health()


@mcp.tool()
def spt_ready() -> str:
    """Check qa Specs readiness (k6, deps)."""
    return tools.spt_ready()


@mcp.tool()
def spt_list_services() -> str:
    """List catalog services."""
    return tools.spt_list_services()


@mcp.tool()
def spt_list_apis(service: str, environment: str | None = None) -> str:
    """List APIs for a catalog service."""
    return tools.spt_list_apis(service, environment)


@mcp.tool()
def spt_resolve_target(service: str, environment: str | None = None) -> str:
    """Resolve target URL for a service/environment."""
    return tools.spt_resolve_target(service, environment)


@mcp.tool()
def spt_list_profiles(
    service: str | None = None,
    environment: str | None = None,
    audience: str | None = None,
) -> str:
    """List test profiles/configs."""
    return tools.spt_list_profiles(service, environment, audience)


@mcp.tool()
def spt_get_profile(config_id: str) -> str:
    """Get one profile by id."""
    return tools.spt_get_profile(config_id)


@mcp.tool()
def spt_list_runs(
    limit: int = 10,
    offset: int = 0,
    service: str | None = None,
    config_id: str | None = None,
    status: str | None = None,
) -> str:
    """List recent runs."""
    return tools.spt_list_runs(limit, offset, service, config_id, status)


@mcp.tool()
def spt_get_run(run_id: str) -> str:
    """Get run detail."""
    return tools.spt_get_run(run_id)


@mcp.tool()
def spt_get_run_live(run_id: str) -> str:
    """Get run with live progress fields."""
    return tools.spt_get_run_live(run_id)


@mcp.tool()
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
    """Start a Specs run (mutating)."""
    return tools.spt_execute_run(
        config_id=config_id,
        audience=audience,
        service=service,
        vus=vus,
        iterations=iterations,
        duration=duration,
        profile=profile,
        triggered_by=triggered_by,
        wait=wait,
    )


@mcp.tool()
def spt_stop_run(run_id: str) -> str:
    """Stop a running Specs run (mutating)."""
    return tools.spt_stop_run(run_id)


@mcp.tool()
def spt_list_traces(run_id: str, limit: int = 50, offset: int = 0) -> str:
    """List traces for a run."""
    return tools.spt_list_traces(run_id, limit, offset)


@mcp.tool()
def spt_compare_runs(run_a: str, run_b: str) -> str:
    """Compare two runs."""
    return tools.spt_compare_runs(run_a, run_b)


if __name__ == "__main__":
    mcp.run()
