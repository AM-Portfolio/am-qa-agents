"""SPT Control MCP — FastMCP tools/resources/prompts wrapping domain services."""

# Do NOT use `from __future__ import annotations` here: FastMCP introspects
# parameter annotations with issubclass(), which fails on postponed string forms.

import json
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from specs import services
from specs.load.config_builder import config_from_request, ensure_default_config
from specs.persistence.run_store import delete_config, get_run, save_config
from specs.schemas import TestConfigIn

mcp = FastMCP(
    "am-test-agent",
    instructions=(
        "AM Test Agent control plane — list profiles, execute API/UI/mixed runs, "
        "poll live progress, inspect traces. Prefer spt_get_run_live for polling. Lists are slim."
    ),
)


@mcp.tool(name="spt_health")
def spt_health() -> dict[str, Any]:
    return services.health()


@mcp.tool(name="spt_list_services")
def spt_list_services() -> dict[str, Any]:
    return services.list_services()


@mcp.tool(name="spt_list_apis")
def spt_list_apis(service: str, environment: Optional[str] = None) -> dict[str, Any]:
    return services.list_apis(service, environment)


@mcp.tool(name="spt_resolve_target")
def spt_resolve_target(service: str, environment: Optional[str] = None) -> dict[str, Any]:
    return services.resolve_target(service, environment)


@mcp.tool(name="spt_openapi_versions")
def spt_openapi_versions(service: str) -> dict[str, Any]:
    return services.openapi_versions(service)


@mcp.tool(name="spt_list_profiles")
def spt_list_profiles(
    service: Optional[str] = None,
    environment: Optional[str] = None,
    audience: Optional[str] = None,
) -> dict[str, Any]:
    rows = services.profiles_list(service=service, environment=environment, audience=audience)
    return {"profiles": rows, "count": len(rows)}


@mcp.tool(name="spt_get_profile")
def spt_get_profile(config_id: str) -> dict[str, Any]:
    row = services.profile_get(config_id)
    return row or {"error": "not_found"}


@mcp.tool(name="spt_create_profile")
def spt_create_profile(profile_json: str) -> dict[str, Any]:
    data = json.loads(profile_json) if isinstance(profile_json, str) else profile_json
    body = TestConfigIn.model_validate(data)
    return save_config(config_from_request(body))


@mcp.tool(name="spt_update_profile")
def spt_update_profile(config_id: str, patch_json: str) -> dict[str, Any]:
    existing = services.profile_get(config_id)
    if not existing:
        return {"error": "not_found"}
    patch = json.loads(patch_json) if isinstance(patch_json, str) else patch_json
    existing.update({k: v for k, v in patch.items() if v is not None})
    existing["id"] = config_id
    return save_config(existing)


@mcp.tool(name="spt_delete_profile")
def spt_delete_profile(config_id: str) -> dict[str, Any]:
    return {"ok": delete_config(config_id)}


@mcp.tool(name="spt_ensure_default_profiles")
def spt_ensure_default_profiles() -> dict[str, Any]:
    return ensure_default_config()


@mcp.tool(name="spt_list_runs")
def spt_list_runs(
    limit: int = 10,
    offset: int = 0,
    service: Optional[str] = None,
    config_id: Optional[str] = None,
    status: Optional[str] = None,
) -> dict[str, Any]:
    return services.runs_list(
        limit=limit, offset=offset, service=service, config_id=config_id, status=status
    )


@mcp.tool(name="spt_get_run")
def spt_get_run(run_id: str) -> dict[str, Any]:
    row = services.run_get(run_id)
    return row or {"error": "not_found"}


@mcp.tool(name="spt_get_run_live")
def spt_get_run_live(run_id: str) -> dict[str, Any]:
    row = services.run_live(run_id)
    return row or {"error": "not_found"}


@mcp.tool(name="spt_running_count")
def spt_running_count() -> dict[str, Any]:
    from specs.persistence.run_store import count_running

    return {"running": count_running()}


@mcp.tool(name="spt_execute_run")
def spt_execute_run(
    config_id: Optional[str] = None,
    audience: Optional[str] = None,
    service: Optional[str] = None,
    vus: Optional[int] = None,
    iterations: Optional[int] = None,
    duration: Optional[str] = None,
    profile: Optional[str] = None,
    triggered_by: str = "mcp",
    wait: bool = False,
) -> dict[str, Any]:
    from specs.security.acl import Caller
    from specs.services.execute_svc import execute_run_sync

    return execute_run_sync(
        config_id=config_id,
        audience=audience,
        service=service,
        vus=vus,
        iterations=iterations,
        duration=duration,
        profile=profile,
        triggered_by=triggered_by,
        wait=wait,
        caller=Caller(role="agent" if audience and audience != "developer" else "developer"),
    )


@mcp.tool(name="spt_stop_run")
def spt_stop_run(run_id: str) -> dict[str, Any]:
    from specs.load.runners import process_registry
    from specs.persistence.run_store import get_run, update_run
    from datetime import datetime, timezone

    row = get_run(run_id)
    if not row:
        return {"error": "not_found"}
    if row.get("status") != "running":
        return {"ok": True, "status": row.get("status"), "message": "already finished"}
    stop_result = process_registry.request_stop(run_id)
    update_run(
        run_id,
        {
            "status": "cancelled",
            "passed": False,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error": "stopped by user",
            "live": {"phase": "cancelled", "message": "Stopped by user"},
        },
    )
    return {"ok": True, "status": "cancelled", "stop": stop_result}

@mcp.tool(name="spt_compare_runs")
def spt_compare_runs(run_a: str, run_b: str) -> dict[str, Any]:
    return services.compare_runs(run_a, run_b)


@mcp.tool(name="spt_list_traces")
def spt_list_traces(
    run_id: str, limit: int = 50, offset: int = 0, api_id: Optional[str] = None
) -> dict[str, Any]:
    return services.traces_list(run_id, limit=limit, offset=offset, api_id=api_id)


@mcp.tool(name="spt_get_trace")
def spt_get_trace(run_id: str, index: int) -> dict[str, Any]:
    row = services.trace_get(run_id, index)
    return row or {"error": "not_found"}


@mcp.tool(name="spt_list_payload_sets")
def spt_list_payload_sets(service: str) -> dict[str, Any]:
    return services.payload_sets(service)


@mcp.tool(name="spt_get_payload_set")
def spt_get_payload_set(service: str, version: Optional[int] = None) -> dict[str, Any]:
    row = services.payload_set_get(service, version)
    return row or {"error": "not_found"}


@mcp.tool(name="spt_activate_payload_set")
def spt_activate_payload_set(service: str, version: int) -> dict[str, Any]:
    return services.activate_payload_set(service, version)


@mcp.tool(name="spt_list_payloads")
def spt_list_payloads(service: Optional[str] = None, api_id: Optional[str] = None) -> dict[str, Any]:
    rows = services.payloads_list(service=service, api_id=api_id)
    return {"payloads": rows, "count": len(rows)}


@mcp.tool(name="spt_upsert_payload")
def spt_upsert_payload(payload_json: str) -> dict[str, Any]:
    data = json.loads(payload_json) if isinstance(payload_json, str) else payload_json
    return services.upsert_payload(data)


@mcp.tool(name="spt_build_payload")
def spt_build_payload(
    service: str,
    environment: Optional[str] = None,
    method: Optional[str] = None,
    path: Optional[str] = None,
    operation_id: Optional[str] = None,
    api_id: Optional[str] = None,
) -> dict[str, Any]:
    """Schema-first payload from live OpenAPI (+ overlay). No LLM."""
    from specs.payloads.payload_pipeline import build_payload

    return build_payload(
        service=service,
        environment=environment,
        method=method,
        path=path,
        operation_id=operation_id,
        api_id=api_id,
    )


@mcp.tool(name="spt_ensure_working_payload")
def spt_ensure_working_payload(
    service: str,
    environment: Optional[str] = None,
    method: Optional[str] = None,
    path: Optional[str] = None,
    operation_id: Optional[str] = None,
    api_id: Optional[str] = None,
    write_back: bool = True,
    allow_llm: Optional[bool] = None,
) -> dict[str, Any]:
    """Build → Try → write set+overlay on 2xx. LLM only if allow_llm / env flag."""
    import asyncio
    import concurrent.futures

    from specs.payloads.payload_pipeline import ensure_working_payload

    coro = ensure_working_payload(
        service=service,
        environment=environment,
        method=method,
        path=path,
        operation_id=operation_id,
        api_id=api_id,
        write_back=write_back,
        allow_llm=allow_llm,
    )
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


@mcp.tool(name="spt_prepare_mcp_payloads")
def spt_prepare_mcp_payloads(
    service: Optional[str] = None,
    environment: Optional[str] = None,
    write_overlays: bool = True,
    try_each: bool = False,
) -> dict[str, Any]:
    """Map real portfolioId / PORTFOLIO {id} from MCP into all OpenAPI ops that need them."""
    from specs.payloads.payload_pipeline import prepare_mcp_payloads, prepare_mcp_payloads_for_service

    if service:
        return prepare_mcp_payloads_for_service(
            service=service,
            environment=environment,
            write_overlays=write_overlays,
            try_each=try_each,
        )
    return prepare_mcp_payloads(
        environment=environment,
        write_overlays=write_overlays,
        try_each=try_each,
    )


@mcp.resource("spt://profiles/{config_id}")
def resource_profile(config_id: str) -> str:
    row = services.profile_get(config_id)
    return json.dumps(row or {"error": "not_found"}, default=str)


@mcp.resource("spt://runs/{run_id}")
def resource_run(run_id: str) -> str:
    row = services.run_get(run_id)
    return json.dumps(row or {"error": "not_found"}, default=str)


@mcp.resource("spt://runs/{run_id}/live")
def resource_run_live(run_id: str) -> str:
    row = services.run_live(run_id)
    return json.dumps(row or {"error": "not_found"}, default=str)


@mcp.prompt(name="spt_agent_smoke")
def prompt_agent_smoke() -> str:
    return (
        "1) spt_list_profiles(audience='agent')\n"
        "2) spt_execute_run(config_id=..., triggered_by='mcp')\n"
        "3) Poll spt_get_run_live until status != running\n"
        "4) spt_list_traces + summarize failures\n"
    )


@mcp.prompt(name="spt_dev_load")
def prompt_dev_load() -> str:
    return (
        "Developer multi-load checklist:\n"
        "1) Confirm role=developer API key\n"
        "2) spt_get_profile for load defaults\n"
        "3) spt_execute_run with vus/iterations\n"
        "4) Poll live; compare with previous via spt_compare_runs\n"
    )


def mount_mcp(app: Any) -> None:
    """Mount streamable HTTP MCP under /mcp."""
    import logging

    log = logging.getLogger("specs.mcp")
    try:
        mcp_app = mcp.streamable_http_app()
        app.mount("/mcp", mcp_app)
        log.info("Control MCP mounted at /mcp (streamable HTTP)")
        return
    except Exception as exc:
        log.warning("streamable MCP mount failed: %s", exc)
    try:
        mcp_app = mcp.sse_app()  # type: ignore[attr-defined]
        app.mount("/mcp", mcp_app)
        log.info("Control MCP mounted at /mcp (SSE fallback)")
    except Exception as exc:
        log.exception("Control MCP failed to mount — /mcp will be unavailable: %s", exc)
