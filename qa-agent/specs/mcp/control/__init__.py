"""SPT Control MCP — FastMCP tools/resources/prompts wrapping domain services."""

# Do NOT use `from __future__ import annotations` here: FastMCP introspects
# parameter annotations with issubclass(), which fails on postponed string forms.

import json
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from specs import services
from specs.load.config_builder import config_from_request, ensure_default_config
from specs.persistence.run_store import delete_config, get_run, save_config
from specs.schemas import TestConfigIn

# streamable_http_path="/" so FastAPI mount("/mcp", …) serves at /mcp (not /mcp/mcp).
# stateless_http=True: works under uvicorn without merging FastMCP lifespan.
mcp = FastMCP(
    "am-test-agent",
    instructions=(
        "AM Test Agent control plane — list profiles, execute API/UI/mixed runs, "
        "poll live progress, inspect traces. Prefer spt_get_run_live for polling. Lists are slim."
    ),
    streamable_http_path="/",
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
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
    max_attempts: int = 3,
    prefer_stored: bool = False,
) -> dict[str, Any]:
    """Build → Try → up to max_attempts LLM retries using API responses → write set on 2xx."""
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
        max_attempts=max_attempts,
        prefer_stored=prefer_stored,
    )
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


@mcp.tool(name="spt_generate_all_payloads")
def spt_generate_all_payloads(
    service: str,
    environment: Optional[str] = None,
    try_each: bool = True,
    write_back: bool = True,
    allow_llm: bool = True,
    prefer_stored: bool = True,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Batch prepare working payloads for all Specs OpenAPI APIs of a service."""
    import asyncio
    import concurrent.futures

    from specs.payloads.payload_pipeline import generate_all_payloads

    coro = generate_all_payloads(
        service=service,
        environment=environment,
        try_each=try_each,
        write_back=write_back,
        allow_llm=allow_llm,
        prefer_stored=prefer_stored,
        max_attempts=max_attempts,
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


@mcp.tool(name="spt_onboard_service")
def spt_onboard_service(
    service: str,
    environment: str = "dev",
    allow_llm: bool = True,
    strict_payloads: bool = False,
    strict_smoke: bool = False,
    plugin_id: Optional[str] = None,
    wait: bool = False,
    use_temporal: bool = True,
) -> dict[str, Any]:
    """Run Specs onboard prep (OpenAPI → tools → auth → payloads → smoke) via Temporal.

    Returns workflow_id + mode, or full OnboardReport (steps[]) when wait=true / inline.
    Poll with spt_onboard_status or GET /api/services/{service}/onboard/{workflow_id}.
    dig environment is normalized to dev.
    """
    import asyncio
    import concurrent.futures

    from orchestrator import temporal_api as tapi

    async def _run() -> dict[str, Any]:
        return await tapi.start_or_run_service_onboard(
            service=service,
            environment=environment,
            allow_llm=allow_llm,
            strict_payloads=strict_payloads,
            strict_smoke=strict_smoke,
            plugin_id=plugin_id,
            use_temporal=use_temporal,
            wait=wait,
        )

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_run())
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _run()).result()


@mcp.tool(name="spt_onboard_status")
def spt_onboard_status(
    workflow_id: str,
    service: Optional[str] = None,
    environment: Optional[str] = None,
) -> dict[str, Any]:
    """Poll onboard workflow result (steps[]) or latest.json when Temporal is down."""
    import asyncio
    import concurrent.futures

    from orchestrator import temporal_api as tapi
    from orchestrator.activities.onboard_report import load_latest_report, normalize_env
    from specs.config import settings

    async def _run() -> dict[str, Any]:
        try:
            return await tapi.get_service_onboard_result(workflow_id)
        except Exception as exc:  # noqa: BLE001
            if service:
                latest = load_latest_report(
                    settings.data_dir,
                    service,
                    normalize_env(environment or settings.default_environment),
                )
                if latest and latest.get("workflow_id") == workflow_id:
                    return {
                        "workflow_id": workflow_id,
                        "status": "COMPLETED",
                        "result": latest,
                        "mode": "latest_json",
                    }
            return {"workflow_id": workflow_id, "error": str(exc)}

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_run())
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _run()).result()


@mcp.tool(name="spt_refresh_openapi_tools")
def spt_refresh_openapi_tools(
    environment: Optional[str] = "prod",
    service: Optional[str] = None,
) -> dict[str, Any]:
    """Fetch prod (or env) Swagger for catalog services and regenerate MCP API tools."""
    from specs.openapi_tools.registry import refresh_tools_from_prod

    services = [service] if service else None
    return refresh_tools_from_prod(environment=environment or "prod", services=services)


@mcp.tool(name="spt_list_openapi_tools")
def spt_list_openapi_tools(
    service: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 200,
) -> dict[str, Any]:
    """List generated OpenAPI tools (from last spt_refresh_openapi_tools)."""
    from specs.openapi_tools.registry import list_tools

    return list_tools(service=service, q=q, limit=limit)


@mcp.tool(name="spt_call_openapi_tool")
def spt_call_openapi_tool(
    name: str,
    arguments_json: Optional[str] = None,
    with_identity_auth: bool = True,
    record_run: bool = True,
    environment: Optional[str] = None,
) -> dict[str, Any]:
    """Call a generated OpenAPI tool by name; arguments_json is a JSON object string.

    Pass environment (dev|dig|preprod|prod) so identity JWT matches the target host.
    """
    from specs.openapi_tools.registry import call_tool

    args: dict[str, Any] = {}
    if arguments_json:
        try:
            parsed = json.loads(arguments_json)
            if isinstance(parsed, dict):
                args = parsed
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"invalid arguments_json: {exc}"}
    return call_tool(
        name,
        args,
        with_identity_auth=with_identity_auth,
        record_run=record_run,
        environment=environment,
    )


# --- QA service plugins + scenario-bank (LiteLLM) ---


@mcp.tool(name="qa_bank_llm_status")
def qa_bank_llm_status(ping_chat: bool = False) -> dict[str, Any]:
    """Probe LiteLLM for scenario-bank invent. Uses LITELLM_BASE_URL + LITELLM_MASTER_KEY. Never returns the key."""
    from ui_evidence.scenario_bank.llm_status import probe_litellm

    return probe_litellm(ping_chat=ping_chat)


@mcp.tool(name="qa_plugin_list")
def qa_plugin_list(include_disabled: bool = False) -> dict[str, Any]:
    """List QA service plugins (am.qa.plugin/v1)."""
    from ui_evidence.plugins.loader import list_plugins

    rows = list_plugins(include_disabled=include_disabled)
    return {"plugins": rows, "count": len(rows)}


@mcp.tool(name="qa_plugin_get")
def qa_plugin_get(
    plugin_id: Optional[str] = None,
    suite: Optional[str] = None,
    api_pack: Optional[str] = None,
) -> dict[str, Any]:
    """Get one plugin by id, suite, or api_pack."""
    from ui_evidence.plugins.loader import get_plugin

    p = get_plugin(plugin_id=plugin_id, suite=suite, api_pack=api_pack, include_disabled=True)
    if not p:
        return {"error": "not_found"}
    return p.summary()


@mcp.tool(name="qa_plugin_reload")
def qa_plugin_reload() -> dict[str, Any]:
    """Rescan qa-agent/plugins/ from disk."""
    from ui_evidence.plugins.loader import reload_plugins

    return reload_plugins()


@mcp.tool(name="qa_plugin_catalog")
def qa_plugin_catalog(plugin_id: str) -> dict[str, Any]:
    """API + UI + feature catalog for a plugin."""
    from ui_evidence.plugins.loader import catalog_bundle, get_plugin

    p = get_plugin(plugin_id=plugin_id, include_disabled=True)
    if not p:
        return {"error": "not_found", "plugin_id": plugin_id}
    return catalog_bundle(p)


@mcp.tool(name="qa_plugin_onboard")
def qa_plugin_onboard(
    plugin_id: str,
    env: str = "dev",
    force_llm: bool = False,
    skip_prep: bool = False,
) -> dict[str, Any]:
    """Onboard plugin: contract smoke + seed prep. Invent uses LiteLLM when available (Phase 5)."""
    from ui_evidence.plugins.onboard import onboard_plugin
    from ui_evidence.scenario_bank.llm_status import probe_litellm

    llm = probe_litellm(ping_chat=False)
    result = onboard_plugin(
        plugin_id, env, force_llm=force_llm, skip_prep=skip_prep
    )
    result["litellm"] = {
        "available": llm.get("available"),
        "model": llm.get("model"),
        "models_count": llm.get("models_count"),
        "error": llm.get("error"),
    }
    if force_llm and not llm.get("available"):
        result["llm_blocked"] = True
        result["note"] = (result.get("note") or "") + "; LiteLLM unavailable — invent skipped"
    return result


@mcp.tool(name="qa_plugin_prep")
def qa_plugin_prep(plugin_id: str, env: str = "dev") -> dict[str, Any]:
    """Run plugin data_prep.entry (fail-closed on env=dev)."""
    from ui_evidence.plugins.loader import get_plugin, run_data_prep

    p = get_plugin(plugin_id=plugin_id)
    if not p:
        return {"ok": False, "error": "not_found", "plugin_id": plugin_id}
    return run_data_prep(p, env)


@mcp.tool(name="qa_bank_list")
def qa_bank_list(service_key: str, env: str = "dev") -> dict[str, Any]:
    """List scenario-bank rows for (service_key, env). Cap 200; dig→dev."""
    from ui_evidence.scenario_bank.bank_store import load_bank

    data = load_bank(service_key, env)
    scenarios = list(data.get("scenarios") or [])
    return {
        "ok": True,
        "service_key": data.get("service_key") or service_key,
        "env": data.get("env") or env,
        "count": len(scenarios),
        "invent_complete": bool(data.get("invent_complete")),
        "needs_reinvent": bool(data.get("needs_reinvent")),
        "scenarios": scenarios,
        "path": data.get("path"),
    }


@mcp.tool(name="qa_bank_select")
def qa_bank_select(
    service_key: str,
    env: str = "dev",
    limit: int = 6,
) -> dict[str, Any]:
    """Select-few scenarios after env policy (Contabo/prod blocks L5/security)."""
    from ui_evidence.scenario_bank.bank_store import list_scenarios
    from ui_evidence.scenario_bank.env_policy import select_few

    rows = list_scenarios(service_key, env)
    result = select_few(rows, env, limit=limit)
    result["ok"] = True
    result["service_key"] = service_key
    return result


@mcp.tool(name="qa_plugin_run_pack")
def qa_plugin_run_pack(
    api_pack: str,
    env: str = "dev",
    skip_prep: bool = False,
) -> dict[str, Any]:
    """Select/prep/execute plugin API pack. Fail-closed on env=dev. No invent."""
    from ui_evidence.plugins.pack_runner import run_api_pack

    return run_api_pack(api_pack, env, skip_prep=skip_prep)


@mcp.tool(name="qa_plugin_set_enabled")
def qa_plugin_set_enabled(plugin_id: str, enabled: bool) -> dict[str, Any]:
    """Enable/disable plugin via plugin.state.yaml sidecar."""
    from ui_evidence.plugins.loader import set_plugin_enabled

    return set_plugin_enabled(plugin_id, enabled)


@mcp.tool(name="qa_credential_list")
def qa_credential_list(
    env: Optional[str] = None,
    kind: Optional[str] = None,
) -> dict[str, Any]:
    """List named QA credentials (no secrets). Seeds SPT login when env is set."""
    from specs.security.credential_store import list_credentials, seed_from_spt_env

    seed_from_spt_env()
    rows = list_credentials(env=env, kind=kind)
    return {"ok": True, "credentials": rows, "count": len(rows)}


@mcp.tool(name="qa_credential_upsert")
def qa_credential_upsert(
    name: str,
    kind: str = "identity_login",
    env: str = "prod",
    username: str = "",
    password: Optional[str] = None,
    token: Optional[str] = None,
    base_url: str = "",
    id: Optional[str] = None,
) -> dict[str, Any]:
    """Create/update a named credential. Secrets never returned."""
    from specs.security.credential_store import CredentialStoreError, upsert_credential

    try:
        row = upsert_credential(
            id=id,
            name=name,
            kind=kind,
            env=env,
            username=username,
            password=password,
            token=token,
            base_url=base_url,
        )
        return {"ok": True, "credential": row}
    except CredentialStoreError as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool(name="qa_credential_delete")
def qa_credential_delete(credential_id: str) -> dict[str, Any]:
    """Delete a named credential by id."""
    from specs.security.credential_store import delete_credential

    ok = delete_credential(credential_id)
    return {"ok": ok, "deleted": credential_id if ok else None}


@mcp.tool(name="qa_flow_list")
def qa_flow_list(
    group: Optional[str] = None,
    category: Optional[str] = None,
) -> dict[str, Any]:
    """List builtin FLOW_*, pack: joins, and authored flows (optional group/category)."""
    from specs.flows.catalog import list_flows

    rows = list_flows(group=group, category=category)
    return {"ok": True, "flows": rows, "count": len(rows)}


@mcp.tool(name="qa_flow_get")
def qa_flow_get(flow_id: str) -> dict[str, Any]:
    """Get a flow document (nodes + edges)."""
    from specs.flows.catalog import get_flow

    doc = get_flow(flow_id)
    if not doc:
        return {"ok": False, "error": f"flow not found: {flow_id}"}
    return {"ok": True, "flow": doc}


@mcp.tool(name="qa_flow_graph")
def qa_flow_graph(flow_id: str) -> dict[str, Any]:
    """Portal/MCP graph payload (layout hints + edges) for a flow."""
    from specs.flows.graph import build_graph

    g = build_graph(flow_id)
    if not g:
        return {"ok": False, "error": f"flow not found: {flow_id}"}
    return {"ok": True, "graph": g}


@mcp.tool(name="qa_flow_upsert")
def qa_flow_upsert(
    title: str,
    nodes: list[dict[str, Any]],
    flow_id: Optional[str] = None,
    gate: str = "prod_safe",
    credential_id: Optional[str] = None,
    env_default: Optional[str] = None,
    edges: Optional[list[dict[str, Any]]] = None,
    group: str = "other",
    category: str = "general",
    description: str = "",
    tags: Optional[list[str]] = None,
    created_by: str = "authored",
) -> dict[str, Any]:
    """Create/update an authored flow (MCP/headless)."""
    from specs.flows.authored_store import AuthoredFlowError, upsert_authored

    try:
        doc = upsert_authored(
            {
                "id": flow_id,
                "title": title,
                "gate": gate,
                "credential_id": credential_id,
                "env_default": env_default,
                "group": group,
                "category": category,
                "description": description,
                "tags": tags or [],
                "created_by": created_by,
                "nodes": nodes,
                "edges": edges,
            },
            flow_id=flow_id,
        )
        return {"ok": True, "flow": doc}
    except AuthoredFlowError as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool(name="qa_flow_propose_scenarios")
def qa_flow_propose_scenarios(
    service: str,
    group: Optional[str] = None,
    category: Optional[str] = None,
    env: str = "prod",
    max_scenarios: int = 5,
    gate: str = "prod_safe",
    use_llm: bool = True,
) -> dict[str, Any]:
    """Propose new flow use-cases from OpenAPI (+ LiteLLM when available). Does not save — confirm with qa_flow_upsert."""
    from specs.flows.propose import propose_scenarios

    return propose_scenarios(
        service=service,
        group=group,
        category=category,
        env=env,
        max_scenarios=max_scenarios,
        gate=gate,
        use_llm=use_llm,
    )


@mcp.tool(name="qa_flow_schedule_upsert")
def qa_flow_schedule_upsert(
    flow_id: str,
    cron: str,
    env: str = "prod",
    credential_id: Optional[str] = None,
    enabled: bool = True,
) -> dict[str, Any]:
    """Create/update a cron schedule for a flow (Temporal when available, else local ticker)."""
    from specs.flows.schedule_store import ScheduleError
    from specs.flows.scheduler import upsert_and_sync

    try:
        return {"ok": True, "schedule": upsert_and_sync(
            flow_id=flow_id,
            cron=cron,
            env=env,
            credential_id=credential_id,
            enabled=enabled,
        )}
    except ScheduleError as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool(name="qa_flow_schedule_list")
def qa_flow_schedule_list(flow_id: Optional[str] = None) -> dict[str, Any]:
    """List flow schedules."""
    from specs.flows.schedule_store import list_schedules

    rows = list_schedules(flow_id=flow_id)
    return {"ok": True, "schedules": rows, "count": len(rows)}


@mcp.tool(name="qa_flow_schedule_disable")
def qa_flow_schedule_disable(schedule_id: str) -> dict[str, Any]:
    """Disable a flow schedule."""
    from specs.flows.schedule_store import disable_schedule
    from specs.flows.scheduler import sync_schedule_temporal
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    row = disable_schedule(schedule_id)
    if not row:
        return {"ok": False, "error": f"schedule not found: {schedule_id}"}

    def _sync() -> dict:
        return asyncio.run(sync_schedule_temporal(row))

    with ThreadPoolExecutor(max_workers=1) as pool:
        sync = pool.submit(_sync).result(timeout=45)
    return {"ok": True, "schedule": row, "sync": sync}


@mcp.tool(name="qa_flow_delete")
def qa_flow_delete(flow_id: str) -> dict[str, Any]:
    """Delete an authored flow (builtin/pack cannot be deleted)."""
    from specs.flows.authored_store import delete_authored

    ok = delete_authored(flow_id)
    return {"ok": ok, "deleted": flow_id if ok else None}


@mcp.tool(name="qa_flow_execute")
def qa_flow_execute(
    flow_id: str,
    env: str = "prod",
    credential_id: Optional[str] = None,
    variables_json: Optional[str] = None,
    payload_set_version: Optional[int] = None,
) -> dict[str, Any]:
    """Start stepped flow execution. Poll with qa_flow_execution_get."""
    from specs.flows.runner import start_execution

    variables = None
    if variables_json:
        variables = (
            json.loads(variables_json)
            if isinstance(variables_json, str)
            else variables_json
        )
    try:
        out = start_execution(
            flow_id,
            env=env,
            credential_id=credential_id,
            variables=variables if isinstance(variables, dict) else None,
            payload_set_version=payload_set_version,
        )
        return {"ok": True, **out}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool(name="qa_flow_runtime_get")
def qa_flow_runtime_get(flow_id: str) -> dict[str, Any]:
    """Get flow runtime: env/credential defaults, variables, Specs payload sets + active/selected version."""
    from specs.flows.runtime import get_runtime

    row = get_runtime(flow_id)
    if not row:
        return {"ok": False, "error": f"flow not found: {flow_id}"}
    return {"ok": True, **row}


@mcp.tool(name="qa_flow_variables_set")
def qa_flow_variables_set(
    flow_id: str,
    variables_json: str,
    payload_set_version: Optional[int] = None,
    clear_payload_pin: bool = False,
) -> dict[str, Any]:
    """Persist custom variables (and optional Specs payload version pin) on a flow."""
    from specs.flows.authored_store import AuthoredFlowError
    from specs.flows.runtime import set_variables

    try:
        variables = (
            json.loads(variables_json)
            if isinstance(variables_json, str)
            else variables_json
        )
        if not isinstance(variables, dict):
            return {"ok": False, "error": "variables_json must be a JSON object"}
        row = set_variables(
            flow_id,
            variables,
            payload_set_version=payload_set_version,
            clear_payload_pin=clear_payload_pin,
        )
        return {"ok": True, **row}
    except (AuthoredFlowError, json.JSONDecodeError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool(name="qa_flow_payload_version_set")
def qa_flow_payload_version_set(
    version: int,
    flow_id: Optional[str] = None,
    service: Optional[str] = None,
    activate: bool = True,
    pin_on_flow: bool = True,
) -> dict[str, Any]:
    """Activate Specs payload-set version for a service and optionally pin it on a flow."""
    from specs.flows.authored_store import AuthoredFlowError
    from specs.flows.runtime import set_payload_version

    try:
        return set_payload_version(
            flow_id=flow_id,
            service=service,
            version=version,
            activate=activate,
            pin_on_flow=pin_on_flow,
        )
    except (AuthoredFlowError, ValueError, FileNotFoundError) as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool(name="qa_flow_payload_api_upsert")
def qa_flow_payload_api_upsert(
    service: str,
    api_id: str,
    payload_json: str,
    version: Optional[int] = None,
    bump_set: bool = False,
) -> dict[str, Any]:
    """Upsert one API's request/response inside a Specs payload set (same as Specs Data tab)."""
    from specs.payloads.payload_store import upsert_api_in_payload_set

    try:
        payload = (
            json.loads(payload_json) if isinstance(payload_json, str) else payload_json
        )
        if not isinstance(payload, dict):
            return {"ok": False, "error": "payload_json must be a JSON object"}
        request = payload.get("request") if isinstance(payload.get("request"), dict) else payload
        response = payload.get("response") if isinstance(payload.get("response"), dict) else {}
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        name = str(payload.get("name") or "working")
        out = upsert_api_in_payload_set(
            service,
            api_id,
            version=version,
            request=request,
            response=response,
            meta=meta,
            name=name,
            bump_set=bump_set,
        )
        return {"ok": True, "payload_set": out}
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool(name="qa_flow_suite_preview")
def qa_flow_suite_preview(
    group: Optional[str] = None,
    api_pack: Optional[str] = None,
    category: Optional[str] = None,
) -> dict[str, Any]:
    """List flows matching a suite group or api_pack before running."""
    from specs.flows.runtime import suite_preview

    return suite_preview(group=group, api_pack=api_pack, category=category)


@mcp.tool(name="qa_flow_suite_execute")
def qa_flow_suite_execute(
    flow_ids_json: str,
    env: str = "prod",
    credential_id: Optional[str] = None,
    payload_set_version: Optional[int] = None,
    variables_json: Optional[str] = None,
) -> dict[str, Any]:
    """Run selected flows as a suite (sequential stepped executions)."""
    from specs.flows.runtime import suite_execute

    try:
        flow_ids = (
            json.loads(flow_ids_json)
            if isinstance(flow_ids_json, str)
            else flow_ids_json
        )
        if not isinstance(flow_ids, list):
            return {"ok": False, "error": "flow_ids_json must be a JSON array"}
        variables = None
        if variables_json:
            variables = (
                json.loads(variables_json)
                if isinstance(variables_json, str)
                else variables_json
            )
        return suite_execute(
            flow_ids=[str(x) for x in flow_ids],
            env=env,
            credential_id=credential_id,
            payload_set_version=payload_set_version,
            variables=variables if isinstance(variables, dict) else None,
        )
    except (ValueError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool(name="qa_flow_node_quick_test")
def qa_flow_node_quick_test(
    flow_id: str,
    node_id: str,
    env: str = "prod",
    credential_id: Optional[str] = None,
    variables_json: Optional[str] = None,
) -> dict[str, Any]:
    """Quick-test a single flow node (runs login first if the node requires auth)."""
    from specs.flows.runner import quick_test_node

    variables = None
    if variables_json:
        try:
            variables = (
                json.loads(variables_json)
                if isinstance(variables_json, str)
                else variables_json
            )
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": str(exc)}
    try:
        out = quick_test_node(
            flow_id,
            node_id,
            env=env,
            credential_id=credential_id,
            variables=variables if isinstance(variables, dict) else None,
        )
        return {"ok": bool(out.get("ok")), **out}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool(name="qa_flow_execution_get")
def qa_flow_execution_get(execution_id: str) -> dict[str, Any]:
    """Poll stepped execution status, per-node events, and summary."""
    from specs.flows import executions as ex_store

    row = ex_store.get_execution(execution_id)
    if not row:
        return {"ok": False, "error": f"execution not found: {execution_id}"}
    return {"ok": True, "execution": row}


@mcp.tool(name="qa_flow_executions_list")
def qa_flow_executions_list(
    flow_id: Optional[str] = None,
    env: Optional[str] = None,
    status: Optional[str] = None,
    suite_run_id: Optional[str] = None,
    limit: int = 50,
) -> dict[str, Any]:
    """List recent stepped flow executions (in-memory history)."""
    from specs.flows import executions as ex_store

    rows = ex_store.list_executions(
        flow_id=flow_id,
        env=env,
        status=status,
        suite_run_id=suite_run_id,
        limit=limit,
    )
    return {"ok": True, "executions": rows, "count": len(rows)}


@mcp.tool(name="qa_flow_execution_stop")
def qa_flow_execution_stop(execution_id: str) -> dict[str, Any]:
    """Request stop of a running stepped execution."""
    from specs.flows import executions as ex_store

    ok = ex_store.request_stop(execution_id)
    return {"ok": ok, "stopping": ok, "execution_id": execution_id}


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
    """Expose Control MCP at /mcp (public URL: {ROOT_PATH}/mcp).

    Starlette ``Mount("/mcp")`` only matches ``/mcp/...`` (regex requires a slash).
    Default ``redirect_slashes`` turns bare ``/mcp`` into ``307 Location: /mcp/``,
    which drops Traefik ``ROOT_PATH`` (``/qa``) and steals traffic to finance
    ``am-mcp-server``. Serve ``/mcp`` and ``/mcp/...`` via a custom route with
    no redirect.
    """
    import logging

    from starlette.routing import BaseRoute, Match, NoMatchFound, get_route_path
    from starlette.types import ASGIApp, Receive, Scope, Send

    log = logging.getLogger("specs.mcp")

    class _McpRoute(BaseRoute):
        def __init__(self, asgi: ASGIApp, *, name: str) -> None:
            self.app = asgi
            self.name = name

        def matches(self, scope: Scope) -> tuple[Match, dict[str, Any]]:
            if scope["type"] not in ("http", "websocket"):
                return Match.NONE, {}
            path = get_route_path(scope)
            if path == "/mcp" or path.startswith("/mcp/"):
                return Match.FULL, {"endpoint": self.app}
            return Match.NONE, {}

        async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
            scope = dict(scope)
            path = get_route_path(scope)
            rest = path[len("/mcp") :] or "/"
            if not rest.startswith("/"):
                rest = "/" + rest
            # Child FastMCP routes at "/"; clear root_path so get_route_path == rest.
            scope["path"] = rest
            scope["root_path"] = ""
            if "raw_path" in scope:
                scope["raw_path"] = rest.encode("utf-8")
            await self.app(scope, receive, send)

        def url_path_for(self, name: str, /, **path_params: Any) -> Any:
            raise NoMatchFound(name, path_params)

    def _attach(mcp_app: ASGIApp, name: str) -> None:
        # Insert ahead of API routes so /mcp is not shadowed.
        app.router.routes.insert(0, _McpRoute(mcp_app, name=name))

    try:
        mcp_app = mcp.streamable_http_app()
        _attach(mcp_app, "control_mcp")
        log.info(
            "Control MCP at /mcp (no slash-redirect, path=%s, stateless=%s)",
            getattr(mcp.settings, "streamable_http_path", "?"),
            getattr(mcp.settings, "stateless_http", "?"),
        )
        return
    except Exception as exc:
        log.warning("streamable MCP mount failed: %s", exc)
    try:
        mcp_app = mcp.sse_app()  # type: ignore[attr-defined]
        _attach(mcp_app, "control_mcp_sse")
        log.info("Control MCP at /mcp (SSE fallback, no slash-redirect)")
    except Exception as exc:
        log.exception("Control MCP failed to mount — /mcp will be unavailable: %s", exc)
