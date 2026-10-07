from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from specs.load import load_ops
from specs.load.assets import scripts_bundle
from specs.catalog.catalog_loader import (
    clear_platform_caches,
    default_target_for_service,
    list_registered_services,
    load_catalog,
    load_openapi_document,
    load_registration,
    load_service_apis,
    openapi_versions_by_env,
    platform_bearer_token,
    proxy_try_request,
    reachable_target_for_service,
)
from specs.config import settings
from specs.catalog.openapi_overlay import load_overlay, merge_effective_document
from specs.payloads.payload_pipeline import (
    build_payload,
    ensure_working_payload,
    generate_all_payloads,
    prepare_mcp_payloads,
    prepare_mcp_payloads_for_service,
)
from specs.schemas import (
    OpenapiToolCallRequest,
    OpenapiToolsRunRequest,
    PayloadBuildRequest,
    PayloadEnsureRequest,
    PayloadGenerateAllRequest,
    PayloadImportRequest,
    PayloadPrepareMcpRequest,
)

router = APIRouter(tags=["platform"])

_TRY_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


@router.get("/health")
async def health() -> dict:
    from specs.services import health as svc_health

    return svc_health()


@router.get("/ready")
async def ready() -> dict:
    h = await load_ops.platform_health()
    from specs.persistence.db.engine import db_health, store_mode

    return {"status": "ready", "platform": h, "store": store_mode(), "db": db_health()}


@router.get("/api/catalog")
async def api_catalog() -> dict:
    return load_catalog()


@router.get("/api/services/{service_key}/overview")
async def api_service_overview(
    service_key: str,
    environment: str | None = Query(default=None, description="dev|preprod|prod"),
    runs_limit: int = Query(default=25, ge=1, le=100),
    live_openapi: bool = Query(
        default=False,
        description="If true, fan out live OpenAPI fetches (slow). Default skips for snappy UI.",
    ),
) -> dict:
    """Aggregate catalog + bank + skills + payloads + recent runs for Services page."""
    from specs.services.service_overview import build_service_overview

    return build_service_overview(
        service_key,
        environment=environment,
        runs_limit=runs_limit,
        live_openapi=live_openapi,
    )


@router.post("/api/services/{service}/onboard")
async def api_service_onboard(
    service: str,
    body: dict = Body(default_factory=dict),
) -> dict:
    """Start ServiceOnboardPrepWorkflow (Temporal) or inline Specs prep with step report."""
    from orchestrator import temporal_api as tapi

    b = body if isinstance(body, dict) else {}
    try:
        return await tapi.start_or_run_service_onboard(
            service=service,
            environment=str(b.get("environment") or settings.default_environment or "dev"),
            strict_payloads=bool(b.get("strict_payloads")),
            strict_smoke=bool(b.get("strict_smoke")),
            allow_llm=bool(b.get("allow_llm", True)),
            plugin_id=b.get("plugin_id"),
            use_temporal=bool(b.get("use_temporal", True)),
            wait=bool(b.get("wait")),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/api/services/{service}/onboard/latest")
async def api_service_onboard_latest(
    service: str,
    environment: str | None = Query(default=None, description="dev|preprod|prod"),
) -> dict:
    """Last persisted onboard report ({data_dir}/onboard/{service}/{env}/latest.json)."""
    from orchestrator.activities.onboard_report import load_latest_report, normalize_env

    env = normalize_env(environment or settings.default_environment or "dev")
    report = load_latest_report(settings.data_dir, service, env)
    if not report:
        raise HTTPException(404, f"no onboard report for {service}/{env}")
    return report


@router.get("/api/services/{service}/onboard/{workflow_id}")
async def api_service_onboard_status(service: str, workflow_id: str) -> dict:
    """Poll Temporal for onboard workflow; falls back to latest.json when done offline."""
    from orchestrator import temporal_api as tapi
    from orchestrator.activities.onboard_report import load_latest_report, normalize_env

    try:
        polled = await tapi.get_service_onboard_result(workflow_id)
        if polled.get("result"):
            return polled
        if polled.get("status") == "COMPLETED":
            return polled
        # Still running or no result yet — attach latest if same workflow_id
        latest = load_latest_report(
            settings.data_dir, service, normalize_env(settings.default_environment)
        )
        if latest and latest.get("workflow_id") == workflow_id:
            return {**polled, "result": latest}
        return polled
    except Exception:  # noqa: BLE001
        latest = load_latest_report(
            settings.data_dir, service, normalize_env(settings.default_environment)
        )
        if latest and latest.get("workflow_id") == workflow_id:
            return {"workflow_id": workflow_id, "status": "COMPLETED", "result": latest, "mode": "latest_json"}
        raise HTTPException(404, f"onboard workflow {workflow_id} not found") from None


@router.get("/api/catalog/registrations")
async def api_catalog_registrations() -> dict:
    """Configured SPT registrations (spt.yaml) for Specs UI."""
    services = list_registered_services()
    return {"services": services, "count": len(services)}


@router.get("/api/catalog/{service}/apis")
async def api_service_apis(
    service: str,
    environment: str | None = Query(default=None, description="dev|preprod|prod — picks targets[env]"),
) -> dict:
    env = environment or settings.default_environment
    data = load_service_apis(service, env)
    reg = load_registration(service)
    target = reachable_target_for_service(service, env)
    # target_url last so registration/baked payloads cannot overwrite the reachable URL
    return {
        "service": service,
        "environment": env,
        "runtime": (reg or {}).get("runtime") or data.get("runtime"),
        "openapi_version": data.get("openapi_version"),
        **data,
        "target_url": target,
        "count": len(data.get("apis") or []),
    }


@router.get("/api/catalog/{service}/target")
async def api_service_target(
    service: str,
    environment: str | None = Query(default=None, description="dev|preprod|prod"),
) -> dict:
    """Resolve browser/k6-reachable base URL for service+env (public_* outside cluster)."""
    env = environment or settings.default_environment
    reg = load_registration(service) or {}
    targets = reg.get("targets") if isinstance(reg.get("targets"), dict) else {}
    target = reachable_target_for_service(service, env)
    return {
        "service": service,
        "environment": env,
        "target_url": target,
        "targets": targets,
        "public_key": f"public_{env}",
        "cluster_key": env,
    }


@router.get("/api/catalog/{service}/openapi/document")
async def api_service_openapi_document(
    service: str,
    environment: str | None = Query(default=None),
    effective: bool = Query(default=False, description="Merge SPT overlay examples into document"),
):
    """Raw OpenAPI JSON proxied by SPT (browser-reachable; cluster DNS is not)."""
    meta = load_openapi_document(service, environment)
    if not meta.get("ok") or not isinstance(meta.get("document"), dict):
        raise HTTPException(
            status_code=502,
            detail=meta.get("error") or f"OpenAPI unavailable for {service}",
        )
    doc = meta["document"]
    env = str(meta.get("environment") or environment or settings.default_environment)
    if effective:
        doc, _overlay = merge_effective_document(doc, service, env)
    return JSONResponse(
        content=doc,
        headers={
            "X-SPT-OpenAPI-Source": str(meta.get("openapi_url") or ""),
            "X-SPT-Service": service,
            "X-SPT-Environment": env,
            "X-SPT-OpenAPI-Effective": "1" if effective else "0",
        },
    )


@router.get("/api/catalog/{service}/openapi/effective")
async def api_service_openapi_effective(
    service: str,
    environment: str | None = Query(default=None),
) -> dict:
    """Live OpenAPI merged with SPT-local overlay (examples from ensure-working / sets)."""
    env = environment or settings.default_environment
    meta = load_openapi_document(service, env)
    if not meta.get("ok") or not isinstance(meta.get("document"), dict):
        raise HTTPException(
            status_code=502,
            detail=meta.get("error") or f"OpenAPI unavailable for {service}",
        )
    doc, overlay = merge_effective_document(meta["document"], service, env)
    return {
        "service": service,
        "environment": env,
        "ok": True,
        "version": meta.get("version"),
        "openapi_url": meta.get("openapi_url"),
        "overlay": {
            "updated_at": overlay.get("updated_at"),
            "operation_count": len(overlay.get("operations") or {}),
        },
        "document": doc,
    }


@router.get("/api/catalog/{service}/openapi")
async def api_service_openapi(
    service: str,
    environment: str | None = Query(default=None),
    include_document: bool = Query(default=True, description="Include full OpenAPI JSON"),
    effective: bool = Query(default=False, description="Merge SPT overlay into document"),
) -> dict:
    """Live OpenAPI document + registration config for Swagger-style Specs UI."""
    meta = load_openapi_document(service, environment)
    if include_document and effective and isinstance(meta.get("document"), dict):
        env = str(meta.get("environment") or environment or settings.default_environment)
        doc, overlay = merge_effective_document(meta["document"], service, env)
        meta = {**meta, "document": doc, "overlay": {
            "updated_at": overlay.get("updated_at"),
            "operation_count": len(overlay.get("operations") or {}),
        }}
    if not include_document:
        meta = {**meta, "document": None}
    return meta


@router.post("/api/catalog/{service}/openapi/sync")
async def api_service_openapi_sync(
    service: str,
    environment: str | None = Query(default=None, description="dev|preprod|prod"),
    force: bool = Query(default=True, description="Bust memory cache and re-pull live"),
) -> dict:
    """Pull service openapi.json from registration targets and cache under data_dir.

    No per-service git catalog — Specs lists APIs from this synced document.
    Call when a service starts feeding / exposes a real OpenAPI URL.
    """
    from specs.catalog.openapi_sync import sync_openapi_for_service
    from specs.openapi_tools.registry import tools_from_openapi_document

    out = sync_openapi_for_service(service, environment, force=force)
    env = str(out.get("environment") or environment or settings.default_environment)
    meta = load_openapi_document(service, env)
    doc = meta.get("document") if isinstance(meta.get("document"), dict) else None
    if out.get("ok") and doc:
        tools_meta = tools_from_openapi_document(
            doc,
            service=service,
            base_url=str(meta.get("target_url") or ""),
            environment=env,
            persist=True,
        )
        out["tools_count"] = tools_meta.get("count")
        out["operation_count"] = tools_meta.get("operation_count") or out.get("operation_count")
    return out


@router.get("/api/catalog/{service}/openapi/tools")
async def api_service_openapi_tools(
    service: str,
    environment: str | None = Query(default=None, description="dev|preprod|prod"),
) -> dict:
    """MCP/OpenAPI tools for Specs — same document as Swagger and /apis."""
    from specs.catalog.openapi_import import count_openapi_operations, openapi_to_apis
    from specs.openapi_tools.registry import tools_from_openapi_document

    env = environment or settings.default_environment
    meta = load_openapi_document(service, env)
    doc = meta.get("document") if isinstance(meta.get("document"), dict) else None
    if not meta.get("ok") or not doc:
        raise HTTPException(
            status_code=502,
            detail=meta.get("error") or f"OpenAPI unavailable for {service}",
        )
    target = str(meta.get("target_url") or reachable_target_for_service(service, env) or "")
    tools_meta = tools_from_openapi_document(
        doc,
        service=service,
        base_url=target,
        environment=env,
        persist=True,
    )
    apis = openapi_to_apis(doc, include_mutating=True)
    return {
        "service": service,
        "environment": str(meta.get("environment") or env),
        "ok": True,
        "openapi_url": meta.get("openapi_url"),
        "target_url": target,
        "count": tools_meta.get("count"),
        "operation_count": tools_meta.get("operation_count")
        or count_openapi_operations(doc),
        "apis_count": len(apis),
        "tools": tools_meta.get("tools") or [],
    }


def _ensure_openapi_tools_for_service(service: str, environment: str | None) -> dict:
    """Refresh registry tools from the same OpenAPI document as Specs list."""
    from specs.openapi_tools.registry import tools_from_openapi_document

    env = environment or settings.default_environment
    meta = load_openapi_document(service, env)
    doc = meta.get("document") if isinstance(meta.get("document"), dict) else None
    if not meta.get("ok") or not doc:
        raise HTTPException(
            status_code=502,
            detail=meta.get("error") or f"OpenAPI unavailable for {service}",
        )
    target = str(meta.get("target_url") or reachable_target_for_service(service, env) or "")
    tools_meta = tools_from_openapi_document(
        doc,
        service=service,
        base_url=target,
        environment=env,
        persist=True,
    )
    return {
        "environment": str(meta.get("environment") or env),
        "target_url": target,
        "tools": tools_meta.get("tools") or [],
        "count": tools_meta.get("count") or 0,
    }


def _arguments_from_payload_request(request: dict | None) -> dict:
    """Flatten Specs payload-set request into OpenAPI tool arguments."""
    if not isinstance(request, dict):
        return {}
    args: dict = {}
    for key in ("path_params", "query"):
        block = request.get(key)
        if isinstance(block, dict):
            args.update(block)
    body = request.get("body")
    if isinstance(body, dict):
        args.update(body)
    return args


def _payload_args_for_tool(
    service: str,
    method: str,
    path: str,
    preferred_version: int | None = None,
) -> dict:
    """Best-effort args from payload sets matching method+path.

    Prefer Specs UI selected version when provided, then active, then richest
    sets (Smoke sets with 1–2 APIs must not hide richer invent/working sets).
    """
    from specs.payloads.payload_store import get_payload_set, list_payload_sets

    method_u = (method or "").upper()
    path_s = str(path or "").rstrip("/") or "/"

    def _match_in_set(payload_set: dict | None) -> dict | None:
        if not payload_set:
            return None
        for entry in (payload_set.get("apis") or {}).values():
            if not isinstance(entry, dict):
                continue
            req = entry.get("request") if isinstance(entry.get("request"), dict) else {}
            if str(req.get("method") or "").upper() != method_u:
                continue
            req_path = str(req.get("path") or "").rstrip("/") or "/"
            if req_path != path_s:
                continue
            return _arguments_from_payload_request(req)
        return None

    if preferred_version is not None:
        hit = _match_in_set(get_payload_set(service, int(preferred_version)))
        if hit is not None:
            return hit

    meta = list_payload_sets(service)
    active_ver = meta.get("active_version")
    summaries = list(meta.get("sets") or [])
    # Active first, then richest sets.
    summaries.sort(
        key=lambda s: (
            0 if active_ver is not None and int(s.get("version") or 0) == int(active_ver) else 1,
            -int(s.get("api_count") or 0),
            -int(s.get("version") or 0),
        )
    )
    versions: list[int | None] = []
    for s in summaries:
        try:
            versions.append(int(s.get("version")))
        except (TypeError, ValueError):
            continue
    if not versions:
        versions = [None]

    for ver in versions:
        hit = _match_in_set(get_payload_set(service, ver))
        if hit is not None:
            return hit
    return {}


def _normalize_tool_call_result(
    *,
    name: str,
    arguments: dict,
    result: dict,
    duration_ms: float | None = None,
    method: str | None = None,
    path: str | None = None,
) -> dict:
    return {
        "ok": bool(result.get("ok")),
        "tool": name,
        "method": str(method or result.get("method") or "").upper(),
        "path": path or result.get("path"),
        "url": result.get("url"),
        "status": result.get("status"),
        "body": result.get("body"),
        "error": result.get("error"),
        "duration_ms": duration_ms,
        "arguments_used": arguments,
        "run_id": result.get("run_id"),
        "service": result.get("service"),
        "op_id": result.get("op_id"),
    }


@router.post("/api/catalog/{service}/openapi/tools/call")
async def api_service_openapi_tool_call(service: str, body: OpenapiToolCallRequest) -> dict:
    """Execute one OpenAPI tool (same path as MCP spt_call_openapi_tool)."""
    import time

    from specs.openapi_tools.registry import call_tool, list_tools

    env = body.environment or settings.default_environment
    _ensure_openapi_tools_for_service(service, env)
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    known = {t.get("name") for t in (list_tools(service=service, limit=5000).get("tools") or [])}
    if name not in known:
        raise HTTPException(
            status_code=404,
            detail=f"unknown tool for {service}: {name}",
        )

    tool_row = next(
        (t for t in list_tools(service=service, limit=5000).get("tools") or [] if t.get("name") == name),
        None,
    ) or {}
    method = str(tool_row.get("method") or "")
    path = str(tool_row.get("path") or "")
    args = dict(body.arguments or {})
    if not args:
        args = _payload_args_for_tool(
            service,
            method,
            path,
            preferred_version=body.payload_set_version,
        )

    started = time.perf_counter()
    result = call_tool(
        name,
        args,
        with_identity_auth=body.with_identity_auth,
        record_run=body.record_run,
        environment=env,
    )
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    return _normalize_tool_call_result(
        name=name,
        arguments=args,
        result=result if isinstance(result, dict) else {"ok": False, "error": str(result)},
        duration_ms=duration_ms,
        method=method,
        path=path,
    )


@router.post("/api/catalog/{service}/openapi/tools/run")
async def api_service_openapi_tools_run(service: str, body: OpenapiToolsRunRequest) -> dict:
    """Run selected or all OpenAPI tools for a service sequentially."""
    import time
    from datetime import datetime, timezone

    from specs.openapi_tools.registry import call_tool, list_tools

    env = body.environment or settings.default_environment
    ensured = _ensure_openapi_tools_for_service(service, env)
    catalog = list_tools(service=service, limit=5000).get("tools") or []
    by_name = {str(t.get("name")): t for t in catalog if t.get("name")}

    if body.all:
        names = list(by_name.keys())
        missing: list[str] = []
    elif body.tool_names:
        names = [n for n in body.tool_names if n in by_name]
        missing = [n for n in body.tool_names if n not in by_name]
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide tool_names or set all=true",
        )

    if body.max_tools is not None:
        names = names[: int(body.max_tools)]

    args_by = body.arguments_by_tool or {}
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    results: list[dict] = []
    for name in names:
        row = by_name[name]
        method = str(row.get("method") or "")
        path = str(row.get("path") or "")
        args = dict(args_by.get(name) or {})
        if not args:
            args = _payload_args_for_tool(
                service,
                method,
                path,
                preferred_version=body.payload_set_version,
            )
        t0 = time.perf_counter()
        raw = call_tool(
            name,
            args,
            with_identity_auth=body.with_identity_auth,
            record_run=body.record_run,
            environment=env,
        )
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        results.append(
            _normalize_tool_call_result(
                name=name,
                arguments=args,
                result=raw if isinstance(raw, dict) else {"ok": False, "error": str(raw)},
                duration_ms=duration_ms,
                method=method,
                path=path,
            )
        )

    finished_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    passed = sum(1 for r in results if r.get("ok"))
    failed = len(results) - passed
    return {
        "ok": failed == 0 and len(results) > 0,
        "service": service,
        "environment": ensured.get("environment") or env,
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "results": results,
        "started_at": started_at,
        "finished_at": finished_at,
        "skipped_unknown": missing,
    }


@router.post("/api/payloads/build")
async def api_payloads_build(body: PayloadBuildRequest) -> dict:
    """Schema-first payload build from live OpenAPI (+ overlay). No LLM."""
    return build_payload(
        service=body.service,
        environment=body.environment,
        method=body.method,
        path=body.path,
        operation_id=body.operation_id,
        api_id=body.api_id,
    )


@router.post("/api/payloads/ensure-working")
async def api_payloads_ensure_working(body: PayloadEnsureRequest) -> dict:
    """Build → Try → up to max_attempts with LLM using API response → write set on 2xx."""
    return await ensure_working_payload(
        service=body.service,
        environment=body.environment,
        method=body.method,
        path=body.path,
        operation_id=body.operation_id,
        api_id=body.api_id,
        write_back=body.write_back,
        allow_llm=body.allow_llm,
        max_attempts=body.max_attempts,
        prefer_stored=body.prefer_stored,
    )


@router.post("/api/payloads/generate-all")
async def api_payloads_generate_all(body: PayloadGenerateAllRequest) -> dict:
    """Prepare working payloads for every Specs OpenAPI API (schema → Try → LLM ×3)."""
    return await generate_all_payloads(
        service=body.service,
        environment=body.environment,
        try_each=body.try_each,
        write_back=body.write_back,
        allow_llm=body.allow_llm,
        prefer_stored=body.prefer_stored,
        max_attempts=body.max_attempts,
    )


@router.post("/api/payloads/import")
async def api_payloads_import(body: PayloadImportRequest) -> dict:
    """Import Postman (or other registered) collection + env into a payload set."""
    from specs.import_adapters import import_collection_to_payload_set

    try:
        return import_collection_to_payload_set(
            service=body.service,
            collection=body.collection,
            environment=body.environment,
            format=body.format,
            label=body.label,
            make_active=body.make_active,
            bump_set=body.bump_set,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/api/payloads/prepare-mcp")
async def api_payloads_prepare_mcp(body: PayloadPrepareMcpRequest) -> dict:
    """Scan registered OpenAPI ops and MCP-fill portfolioId / PORTFOLIO {id} placeholders.

    Writes overlays + payload-set entries so Swagger Try and k6 picks up real IDs.
    Pass service=<id> or omit to process all catalog services.
    """
    import asyncio

    from specs.payloads.payload_pipeline import prepare_mcp_payloads, prepare_mcp_payloads_for_service

    services = body.services
    if body.service:
        services = [body.service]

    if services and len(services) == 1:
        return await asyncio.to_thread(
            prepare_mcp_payloads_for_service,
            service=services[0],
            environment=body.environment,
            write_overlays=body.write_overlays,
            try_each=body.try_each,
        )
    return await asyncio.to_thread(
        prepare_mcp_payloads,
        environment=body.environment,
        services=services,
        write_overlays=body.write_overlays,
        try_each=body.try_each,
    )


@router.get("/api/catalog/{service}/openapi/overlay")
async def api_service_openapi_overlay(
    service: str,
    environment: str | None = Query(default=None),
) -> dict:
    env = environment or settings.default_environment
    return load_overlay(service, env)

@router.get("/api/catalog/{service}/openapi/versions")
async def api_service_openapi_versions(service: str) -> dict:
    """OpenAPI info.version (and reachability) per configured environment."""
    versions = openapi_versions_by_env(service)
    return {"service": service, "environments": versions, "count": len(versions)}


@router.get("/api/platform/health")
async def api_platform_health() -> dict:
    return await load_ops.platform_health()


@router.get("/api/platform/try-token")
async def api_platform_try_token(
    environment: str | None = Query(default=None, description="dev|preprod|prod|dig"),
) -> dict:
    """Bearer token for Swagger UI Try it out (platform identity; SPT-owned auth)."""
    from specs.catalog.catalog_loader import _identity_url_for_platform_auth

    env = environment or settings.default_environment
    token = platform_bearer_token(environment=env)
    if not token:
        raise HTTPException(status_code=503, detail="SPT identity login unavailable")
    return {
        "token_type": "Bearer",
        "access_token": token,
        "identity_url": _identity_url_for_platform_auth(env),
        "environment": env,
    }


@router.post("/api/platform/clear-cache")
async def api_platform_clear_cache() -> dict:
    """Clear SPT in-memory OpenAPI + auth token caches (browser also clears local storage)."""
    cleared = clear_platform_caches()
    return {"ok": True, "cleared": cleared}


@router.api_route(
    "/api/catalog/{service}/try/{environment}",
    methods=_TRY_METHODS,
)
@router.api_route(
    "/api/catalog/{service}/try/{environment}/{path:path}",
    methods=_TRY_METHODS,
)
async def api_service_try_proxy(
    service: str,
    environment: str,
    request: Request,
    path: str = "",
) -> Response:
    """Browser-safe Try it out proxy (same-origin → SPT → service). Avoids CORS / cluster DNS."""
    result = await proxy_try_request(
        service,
        environment,
        request.method,
        path,
        query=str(request.url.query or ""),
        headers={k: v for k, v in request.headers.items()},
        body=await request.body(),
    )
    return Response(
        content=result.get("body") or b"",
        status_code=int(result.get("status_code") or 502),
        headers=result.get("headers") or {"content-type": "application/json"},
    )


@router.get("/api/scripts")
async def api_scripts() -> dict:
    return scripts_bundle()


@router.get("/config")
async def config_preview() -> dict:
    from specs.persistence.db.engine import store_mode

    return {
        "poc_target_url": settings.poc_target_url,
        "grafana_public_url": settings.grafana_public_url,
        "minio_console_url": settings.minio_public_console_url,
        "influxdb_bucket": settings.influxdb_bucket,
        "max_vus": settings.max_vus,
        "root_path": settings.root_path or "/",
        "ui_url": f"{settings.root_path.rstrip('/')}/ui" if settings.root_path else "/ui",
        "data_dir": settings.data_dir,
        "runner": "k6-local",
        "spt_store": store_mode(),
        "spt_acl_required": settings.spt_acl_required,
        "max_concurrent_runs": settings.spt_max_concurrent_runs,
        "mcp_path": "/mcp",
    }
