"""Build + Try ensure-working loop with optional LLM fallback + MCP enrich."""
from __future__ import annotations

import json
import logging
from typing import Any

from spt.catalog_loader import load_catalog, load_openapi_document, proxy_try_request
from spt.config import settings
from spt.fin_api_client import llm_suggest_payload
from spt.openapi_overlay import load_overlay, upsert_operation_overlay
from spt.payload_builder import (
    build_query_string,
    build_request_from_operation,
    find_operation,
    operation_key,
)
from spt.payload_store import save_payload, upsert_api_in_payload_set

logger = logging.getLogger(__name__)

_HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")


def _effective_doc(service: str, environment: str) -> tuple[dict[str, Any] | None, dict[str, Any], dict[str, Any]]:
    meta = load_openapi_document(service, environment)
    doc = meta.get("document") if isinstance(meta.get("document"), dict) else None
    overlay = load_overlay(service, environment or settings.default_environment)
    return doc, meta, overlay


def _apply_mcp_enrich(
    built: dict[str, Any],
    *,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mutate a build_payload result with MCP facts (placeholders only)."""
    if not settings.spt_payload_mcp_enrich:
        return {**built, "mcp_attempted": False, "mcp_fields": [], "mcp_error": None}
    if not built.get("ok") or not isinstance(built.get("request"), dict):
        return {**built, "mcp_attempted": False, "mcp_fields": [], "mcp_error": None}

    mcp_error: str | None = None
    mcp_fields: list[str] = []
    request = dict(built["request"])
    source = built.get("source") or "schema"
    try:
        from spt.mcp_data_client import fetch_prep_context
        from spt.mcp_payload_enrich import enrich_request_from_mcp

        use_ctx = ctx if ctx is not None else fetch_prep_context()
        enriched = enrich_request_from_mcp(request, use_ctx)
        if enriched.get("mcp_used") and isinstance(enriched.get("request"), dict):
            request = enriched["request"]
            mcp_fields = list(enriched.get("mcp_fields") or [])
            source = "mcp"
            built = {
                **built,
                "ok": True,
                "request": request,
                "source": source,
            }
    except Exception as exc:
        mcp_error = str(exc)
        logger.warning("MCP enrich failed: %s", exc)

    return {
        **built,
        "mcp_attempted": True,
        "mcp_fields": mcp_fields,
        "mcp_error": mcp_error,
    }


def build_payload(
    *,
    service: str,
    environment: str | None = None,
    method: str | None = None,
    path: str | None = None,
    operation_id: str | None = None,
    api_id: str | None = None,
    enrich_mcp: bool | None = None,
    mcp_ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    env = environment or settings.default_environment
    doc, meta, overlay = _effective_doc(service, env)
    if not doc:
        return {
            "ok": False,
            "error": meta.get("error") or "openapi_unavailable",
            "service": service,
            "environment": env,
        }
    hit = find_operation(doc, method=method, path=path, operation_id=operation_id, api_id=api_id)
    op_key = None
    overlay_entry = None
    if hit:
        op_key = operation_key(hit["method"], hit["path"], hit.get("operation_id"))
        overlay_entry = (overlay.get("operations") or {}).get(op_key)
        if overlay_entry is None and hit.get("operation_id"):
            overlay_entry = (overlay.get("operations") or {}).get(hit["operation_id"])

    built = build_request_from_operation(
        doc,
        method=method,
        path=path,
        operation_id=operation_id,
        api_id=api_id,
        overlay_entry=overlay_entry,
    )
    result = {
        **built,
        "service": service,
        "environment": env,
        "openapi_version": meta.get("version"),
        "operation_key": built.get("operation_key") or op_key,
    }
    do_enrich = settings.spt_payload_mcp_enrich if enrich_mcp is None else enrich_mcp
    if do_enrich:
        result = _apply_mcp_enrich(result, ctx=mcp_ctx)
    return result


def prepare_mcp_payloads_for_service(
    *,
    service: str,
    environment: str | None = None,
    write_overlays: bool = True,
    try_each: bool = False,
) -> dict[str, Any]:
    """Scan all OpenAPI ops; MCP-fill portfolio/symbol placeholders; write overlays.

    Dashboard APIs without portfolio params are skipped (nothing to map).
    """
    env = environment or settings.default_environment
    doc, meta, _overlay = _effective_doc(service, env)
    if not doc:
        return {
            "ok": False,
            "service": service,
            "environment": env,
            "error": meta.get("error") or "openapi_unavailable",
            "mapped": [],
            "skipped": [],
        }

    from spt.mcp_data_client import fetch_prep_context
    from spt.mcp_payload_enrich import is_placeholder

    ctx = fetch_prep_context(force=True)
    mapped: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    paths = doc.get("paths") if isinstance(doc.get("paths"), dict) else {}

    for raw_path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for method in _HTTP_METHODS:
            op = item.get(method)
            if not isinstance(op, dict):
                continue
            built = build_payload(
                service=service,
                environment=env,
                method=method.upper(),
                path=str(raw_path),
                operation_id=str(op.get("operationId") or "") or None,
                enrich_mcp=True,
                mcp_ctx=ctx,
            )
            if not built.get("ok") or not isinstance(built.get("request"), dict):
                skipped.append(
                    {
                        "method": method.upper(),
                        "path": raw_path,
                        "reason": built.get("error") or "build_failed",
                    }
                )
                continue

            req = built["request"]
            mcp_fields = list(built.get("mcp_fields") or [])

            if not mcp_fields:
                # Schema had placeholders but MCP didn't fill, OR no portfolio params
                pp = req.get("path_params") or {}
                q = req.get("query") or {}
                has_portfolio_keys = any(
                    k.lower() in ("portfolioid", "portfolio_id")
                    or (
                        k.lower() == "id"
                        and str(pp.get("type") or q.get("type") or "").upper() == "PORTFOLIO"
                    )
                    for k in list(pp.keys()) + list(q.keys())
                )
                if not has_portfolio_keys:
                    skipped.append(
                        {
                            "method": method.upper(),
                            "path": raw_path,
                            "reason": "no_portfolio_params",
                            "operation_id": req.get("operation_id"),
                        }
                    )
                    continue
                # Has keys but already real values from overlay
                id_val = pp.get("id") or pp.get("portfolioId") or q.get("portfolioId")
                if id_val and not is_placeholder(id_val):
                    skipped.append(
                        {
                            "method": method.upper(),
                            "path": raw_path,
                            "reason": "already_mapped",
                            "operation_id": req.get("operation_id"),
                            "id": id_val,
                        }
                    )
                    continue
                skipped.append(
                    {
                        "method": method.upper(),
                        "path": raw_path,
                        "reason": "mcp_no_fill",
                        "operation_id": req.get("operation_id"),
                    }
                )
                continue

            try_info: dict[str, Any] | None = None
            ok_http = True
            if try_each:
                try_result = _try_once_sync(service, env, req)
                status = int(try_result.get("status_code") or 0)
                ok_http = 200 <= status < 300
                try_info = {
                    "status_code": status,
                    "upstream_url": try_result.get("upstream_url"),
                    "error": try_result.get("error"),
                }
                if not ok_http:
                    mapped.append(
                        {
                            "method": method.upper(),
                            "path": raw_path,
                            "operation_id": req.get("operation_id"),
                            "api_id": req.get("api_id"),
                            "mcp_fields": mcp_fields,
                            "request": req,
                            "try": try_info,
                            "written": False,
                            "ok": False,
                        }
                    )
                    continue

            written = False
            if write_overlays and (not try_each or ok_http):
                op_key = str(
                    built.get("operation_key")
                    or req.get("operation_id")
                    or operation_key(method, str(raw_path), req.get("operation_id"))
                )
                upsert_operation_overlay(
                    service,
                    env,
                    operation_key=op_key,
                    path_params=req.get("path_params") or {},
                    query=req.get("query") or {},
                    body=req.get("body"),
                    source="mcp",
                )
                api_id_val = str(req.get("api_id") or "unknown")
                saved = save_payload(
                    {
                        "service": service,
                        "api_id": api_id_val,
                        "name": "working",
                        "request": {
                            "method": req.get("method"),
                            "path": req.get("path"),
                            "query": req.get("query") or {},
                            "path_params": req.get("path_params") or {},
                            "body": req.get("body"),
                        },
                        "response": {"status": (try_info or {}).get("status_code") or 200},
                        "meta": {"source": "mcp", "prepare_mcp": True},
                    },
                    bump=True,
                )
                upsert_api_in_payload_set(
                    service,
                    api_id_val,
                    request=saved.get("request"),
                    response=saved.get("response"),
                    meta={"source": "mcp"},
                    name="working",
                    bump_set=False,
                )
                written = True

            mapped.append(
                {
                    "method": method.upper(),
                    "path": raw_path,
                    "operation_id": req.get("operation_id"),
                    "api_id": req.get("api_id"),
                    "mcp_fields": mcp_fields,
                    "path_params": req.get("path_params"),
                    "resolved_path": req.get("resolved_path"),
                    "try": try_info,
                    "written": written,
                    "ok": True,
                }
            )

    return {
        "ok": True,
        "service": service,
        "environment": env,
        "portfolio_id": ctx.get("portfolio_id"),
        "symbol": ctx.get("symbol"),
        "mapped_count": len(mapped),
        "skipped_count": len(skipped),
        "mapped": mapped,
        "skipped": skipped,
    }


def _try_once_sync(service: str, environment: str, request: dict[str, Any]) -> dict[str, Any]:
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_try_once(service, environment, request))
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _try_once(service, environment, request)).result()


def prepare_mcp_payloads(
    *,
    environment: str | None = None,
    services: list[str] | None = None,
    write_overlays: bool = True,
    try_each: bool = False,
) -> dict[str, Any]:
    """Map portfolio IDs across one service or all registered catalog services."""
    env = environment or settings.default_environment
    if services:
        ids = [str(s) for s in services if s]
    else:
        cat = load_catalog()
        ids = [str(row.get("id")) for row in (cat.get("services") or []) if row.get("id")]

    results: list[dict[str, Any]] = []
    for sid in ids:
        results.append(
            prepare_mcp_payloads_for_service(
                service=sid,
                environment=env,
                write_overlays=write_overlays,
                try_each=try_each,
            )
        )
    return {
        "ok": True,
        "environment": env,
        "services": len(results),
        "mapped_total": sum(int(r.get("mapped_count") or 0) for r in results),
        "results": results,
    }


async def ensure_working_payload(
    *,
    service: str,
    environment: str | None = None,
    method: str | None = None,
    path: str | None = None,
    operation_id: str | None = None,
    api_id: str | None = None,
    write_back: bool = True,
    allow_llm: bool | None = None,
) -> dict[str, Any]:
    env = environment or settings.default_environment
    built = build_payload(
        service=service,
        environment=env,
        method=method,
        path=path,
        operation_id=operation_id,
        api_id=api_id,
        enrich_mcp=True,
    )
    if not built.get("ok") or not isinstance(built.get("request"), dict):
        return built

    request = dict(built["request"])
    source = built.get("source") or "schema"
    mcp_attempted = bool(built.get("mcp_attempted"))
    mcp_fields = list(built.get("mcp_fields") or [])
    mcp_error = built.get("mcp_error")

    try_result = await _try_once(service, env, request)
    status = int(try_result.get("status_code") or 0)
    ok_http = 200 <= status < 300

    llm_used = False
    if not ok_http and (allow_llm if allow_llm is not None else settings.spt_payload_llm_fallback):
        llm = await llm_suggest_payload(
            service=service,
            method=str(request.get("method") or "GET"),
            path=str(request.get("path") or ""),
            openapi_snippet={"operation_id": request.get("operation_id"), "path": request.get("path")},
            error_hint=f"status={status}",
        )
        llm_used = True
        if llm.get("ok") and isinstance(llm.get("request"), dict):
            suggested = llm["request"]
            request = {
                **request,
                "path_params": suggested.get("path_params") or suggested.get("pathParams") or request.get("path_params"),
                "query": suggested.get("query") or request.get("query"),
                "body": suggested.get("body") if "body" in suggested else request.get("body"),
                "resolved_path": suggested.get("resolved_path") or request.get("resolved_path"),
            }
            if request.get("path") and request.get("path_params"):
                resolved = str(request["path"])
                for k, v in (request.get("path_params") or {}).items():
                    resolved = resolved.replace("{" + k + "}", str(v))
                request["resolved_path"] = resolved
            source = "llm-fallback"
            try_result = await _try_once(service, env, request)
            status = int(try_result.get("status_code") or 0)
            ok_http = 200 <= status < 300

    result: dict[str, Any] = {
        "ok": ok_http,
        "service": service,
        "environment": env,
        "source": source,
        "llm_attempted": llm_used,
        "mcp_attempted": mcp_attempted,
        "mcp_fields": mcp_fields,
        "mcp_error": mcp_error,
        "request": request,
        "try": {
            "status_code": status,
            "upstream_url": try_result.get("upstream_url"),
            "error": try_result.get("error"),
        },
        "operation_key": built.get("operation_key"),
        "api_id": request.get("api_id"),
    }

    if ok_http and write_back:
        op_key = str(built.get("operation_key") or request.get("operation_id") or request.get("api_id"))
        upsert_operation_overlay(
            service,
            env,
            operation_key=op_key,
            path_params=request.get("path_params") or {},
            query=request.get("query") or {},
            body=request.get("body"),
            source=source if source != "schema" else "ensure-working",
        )
        api_id_val = str(request.get("api_id") or "unknown")
        saved = save_payload(
            {
                "service": service,
                "api_id": api_id_val,
                "name": "working",
                "request": {
                    "method": request.get("method"),
                    "path": request.get("path"),
                    "query": request.get("query") or {},
                    "path_params": request.get("path_params") or {},
                    "body": request.get("body"),
                },
                "response": {
                    "status": status,
                },
                "meta": {"source": source, "ensure_working": True},
            },
            bump=True,
        )
        payload_set = upsert_api_in_payload_set(
            service,
            api_id_val,
            request=saved.get("request"),
            response=saved.get("response"),
            meta={"source": source},
            name="working",
            bump_set=False,
        )
        result["payload"] = saved
        result["payload_set"] = {
            "version": payload_set.get("version"),
            "active": True,
        }
        result["overlay_written"] = True

    return result


async def _try_once(service: str, environment: str, request: dict[str, Any]) -> dict[str, Any]:
    path = str(request.get("resolved_path") or request.get("path") or "").lstrip("/")
    query = request.get("query") if isinstance(request.get("query"), dict) else {}
    qs = build_query_string(query) if query else ""
    body_raw: bytes | None = None
    headers = {"Accept": "application/json"}
    if request.get("body") is not None and str(request.get("method") or "GET").upper() not in ("GET", "HEAD"):
        body_raw = json.dumps(request["body"]).encode("utf-8")
        headers["Content-Type"] = "application/json"
    return await proxy_try_request(
        service,
        environment,
        str(request.get("method") or "GET"),
        path,
        query=qs,
        headers=headers,
        body=body_raw,
    )
