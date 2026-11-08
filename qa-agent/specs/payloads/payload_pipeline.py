"""Build + Try ensure-working loop with optional LLM fallback + MCP enrich."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from specs.catalog.catalog_loader import load_catalog, load_openapi_document, proxy_try_request
from specs.config import settings
from specs.legacy.fin_api_client import llm_suggest_payload
from specs.catalog.openapi_overlay import load_overlay, upsert_operation_overlay
from specs.payloads.payload_builder import (
    build_query_string,
    build_request_from_operation,
    find_operation,
    operation_key,
)
from specs.payloads.payload_store import save_payload, upsert_api_in_payload_set

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
        from specs.mcp.mcp_data_client import fetch_prep_context
        from specs.payloads.mcp_payload_enrich import enrich_request_from_mcp

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
    try:
        from specs.catalog.openapi_sync import sync_openapi_for_service

        sync_openapi_for_service(service, env, force=True)
    except Exception:
        pass
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

    from specs.mcp.mcp_data_client import fetch_prep_context
    from specs.payloads.mcp_payload_enrich import is_placeholder

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


def _parse_try_body(try_result: dict[str, Any], *, limit: int = 8000) -> Any:
    """Decode proxy Try body to JSON/object or truncated text for QA UI."""
    body = try_result.get("body")
    if body is None:
        body = try_result.get("response_body") or try_result.get("text")
    if isinstance(body, (bytes, bytearray)):
        text = bytes(body).decode("utf-8", errors="replace")
        try:
            return json.loads(text)
        except Exception:
            return text[:limit]
    if isinstance(body, (dict, list)):
        return body
    if body is None:
        return None
    text = str(body)
    try:
        return json.loads(text)
    except Exception:
        return text[:limit]


def _request_for_ui(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "method": request.get("method"),
        "path": request.get("path"),
        "resolved_path": request.get("resolved_path"),
        "path_params": request.get("path_params") or {},
        "query": request.get("query") or {},
        "body": request.get("body"),
        "api_id": request.get("api_id"),
    }


def _snippet_from_try(try_result: dict[str, Any], *, limit: int = 2000) -> str:
    status = int(try_result.get("status_code") or 0)
    err = str(try_result.get("error") or "").strip()
    parsed = _parse_try_body(try_result, limit=limit)
    if isinstance(parsed, (dict, list)):
        try:
            body_s = json.dumps(parsed, default=str)[:limit]
        except Exception:
            body_s = str(parsed)[:limit]
    else:
        body_s = str(parsed or "")[:limit]
    parts = [f"status={status}"]
    if err:
        parts.append(f"error={err[:400]}")
    if body_s:
        parts.append(f"body={body_s}")
    return " ".join(parts)


def _merge_llm_request(request: dict[str, Any], suggested: dict[str, Any]) -> dict[str, Any]:
    merged = {
        **request,
        "path_params": suggested.get("path_params")
        or suggested.get("pathParams")
        or request.get("path_params"),
        "query": suggested.get("query") or request.get("query"),
        "body": suggested.get("body") if "body" in suggested else request.get("body"),
        "resolved_path": suggested.get("resolved_path") or request.get("resolved_path"),
    }
    if merged.get("path") and merged.get("path_params"):
        resolved = str(merged["path"])
        for k, v in (merged.get("path_params") or {}).items():
            resolved = resolved.replace("{" + k + "}", str(v))
        merged["resolved_path"] = resolved
    return merged


def _write_working_payload(
    *,
    service: str,
    env: str,
    request: dict[str, Any],
    source: str,
    status: int,
    operation_key: str | None,
) -> dict[str, Any]:
    op_key = str(operation_key or request.get("operation_id") or request.get("api_id"))
    upsert_operation_overlay(
        service,
        env,
        operation_key=op_key,
        path_params=request.get("path_params") or {},
        query=request.get("query") or {},
        body=request.get("body"),
        source=source if source not in ("schema", "set") else "ensure-working",
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
            "response": {"status": status},
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
    return {
        "payload": saved,
        "payload_set": {"version": payload_set.get("version"), "active": True},
        "overlay_written": True,
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
    max_attempts: int = 3,
    prefer_stored: bool = False,
    initial_request: dict[str, Any] | None = None,
    initial_source: str | None = None,
) -> dict[str, Any]:
    """Build → Try → optional LLM retries (up to max_attempts) → write set on 2xx.

    Attempt 1 uses stored/schema request; later attempts call LLM with the prior
    API response as error_hint so payloads can be refined from real failures.
    """
    env = environment or settings.default_environment
    llm_enabled = allow_llm if allow_llm is not None else settings.spt_payload_llm_fallback
    max_attempts = max(1, min(int(max_attempts or 3), 5))

    built: dict[str, Any] = {"ok": True, "operation_key": None}
    if isinstance(initial_request, dict) and initial_request.get("method"):
        request = dict(initial_request)
        source = initial_source or "set"
        mcp_attempted = False
        mcp_fields: list[Any] = []
        mcp_error = None
    else:
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
            return {**built, "attempts": [], "attempts_used": 0}
        request = dict(built["request"])
        source = built.get("source") or "schema"
        mcp_attempted = bool(built.get("mcp_attempted"))
        mcp_fields = list(built.get("mcp_fields") or [])
        mcp_error = built.get("mcp_error")

    attempts: list[dict[str, Any]] = []
    llm_used = False
    try_result: dict[str, Any] = {}
    status = 0
    ok_http = False

    for n in range(1, max_attempts + 1):
        if n > 1:
            if not llm_enabled:
                break
            hint = _snippet_from_try(try_result)
            llm = await llm_suggest_payload(
                service=service,
                method=str(request.get("method") or "GET"),
                path=str(request.get("path") or ""),
                openapi_snippet={
                    "operation_id": request.get("operation_id"),
                    "path": request.get("path"),
                    "api_id": request.get("api_id"),
                },
                error_hint=hint,
            )
            llm_used = True
            if not (llm.get("ok") and isinstance(llm.get("request"), dict)):
                attempts.append(
                    {
                        "n": n,
                        "source": "llm-fallback",
                        "status_code": None,
                        "ok": False,
                        "error_snippet": str(llm.get("error") or llm.get("reason") or "llm_failed")[
                            :500
                        ],
                        "request": _request_for_ui(request),
                        "response": None,
                    }
                )
                continue
            request = _merge_llm_request(request, llm["request"])
            source = "llm-fallback"

        try_result = await _try_once(service, env, request)
        status = int(try_result.get("status_code") or 0)
        ok_http = 200 <= status < 300
        response_body = _parse_try_body(try_result)
        attempts.append(
            {
                "n": n,
                "source": source if n == 1 else "llm-fallback",
                "status_code": status,
                "ok": ok_http,
                "error_snippet": _snippet_from_try(try_result, limit=500),
                "request": _request_for_ui(request),
                "response": {
                    "status_code": status,
                    "body": response_body,
                    "error": try_result.get("error"),
                    "upstream_url": try_result.get("upstream_url"),
                },
            }
        )
        if ok_http:
            break

    last_response = {
        "status_code": status,
        "body": _parse_try_body(try_result) if try_result else None,
        "error": try_result.get("error") if try_result else None,
        "upstream_url": try_result.get("upstream_url") if try_result else None,
    }
    result: dict[str, Any] = {
        "ok": ok_http,
        "service": service,
        "environment": env,
        "source": source,
        "llm_attempted": llm_used,
        "mcp_attempted": mcp_attempted,
        "mcp_fields": mcp_fields,
        "mcp_error": mcp_error,
        "request": _request_for_ui(request),
        "response": last_response,
        "try": {
            "status_code": status,
            "upstream_url": try_result.get("upstream_url"),
            "error": try_result.get("error"),
            "body": last_response.get("body"),
        },
        "operation_key": built.get("operation_key"),
        "api_id": request.get("api_id") or api_id,
        "attempts": attempts,
        "attempts_used": len(attempts),
        "final_status": status,
        "error": None if ok_http else _snippet_from_try(try_result, limit=800),
    }

    if ok_http and write_back:
        written = _write_working_payload(
            service=service,
            env=env,
            request=request,
            source=source,
            status=status,
            operation_key=str(built.get("operation_key") or "") or None,
        )
        result.update(written)

    return result


def _harvest_ids_from_body(body: Any) -> dict[str, Any]:
    """Pull likely path-param values from a successful API JSON body."""
    out: dict[str, Any] = {}

    def walk(node: Any, *, depth: int = 0) -> None:
        if depth > 4 or not isinstance(node, dict):
            return
        for k, v in node.items():
            key = str(k)
            if isinstance(v, (str, int)) and str(v).strip():
                if key.endswith("_id") or key in ("id", "uuid", "code", "plan_code", "plan_id"):
                    out[key] = v
                    if key == "id":
                        # Common OpenAPI path param names
                        out.setdefault("subscription_id", v)
                        out.setdefault("id", v)
                    if key == "plan_code":
                        out.setdefault("plan_id", v)
            elif isinstance(v, dict):
                walk(v, depth=depth + 1)
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                walk(v[0], depth=depth + 1)

    walk(body)
    return out


def _apply_run_context(
    request: dict[str, Any],
    ctx: dict[str, Any],
    *,
    prefer_ctx: bool = True,
) -> dict[str, Any]:
    """Fill path params from earlier successes in this generate-all run.

    prefer_ctx=True overwrites schema/example ids with values harvested from
    create/list responses so cancel/pause/resume hit a real resource.
    """
    if not ctx:
        return request
    req = dict(request)
    path = str(req.get("path") or "")
    pp = dict(req.get("path_params") or {})
    changed = False
    for name in re.findall(r"\{([^}]+)\}", path):
        cur = pp.get(name)
        cur_s = str(cur).strip() if cur is not None else ""
        needs = (
            prefer_ctx
            or not cur_s
            or cur_s == "{" + name + "}"
            or cur_s.startswith("{")
            or cur_s in ("string", "uuid", "id", "0", "1")
        )
        if not needs:
            continue
        picked = None
        if name in ctx and ctx[name] is not None:
            picked = ctx[name]
        elif name.endswith("_id") and "id" in ctx:
            picked = ctx["id"]
        elif name == "id" and "subscription_id" in ctx:
            picked = ctx["subscription_id"]
        if picked is not None and str(picked) != cur_s:
            pp[name] = picked
            changed = True
    if changed:
        req["path_params"] = pp
        resolved = path
        for k, v in pp.items():
            resolved = resolved.replace("{" + k + "}", str(v))
        req["resolved_path"] = resolved
    return req


async def generate_all_payloads(
    *,
    service: str,
    environment: str | None = None,
    try_each: bool = True,
    write_back: bool = True,
    allow_llm: bool = True,
    prefer_stored: bool = True,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Prepare working payloads for every Specs OpenAPI API (batch ensure)."""
    from specs.catalog.catalog_loader import load_openapi_document, load_service_apis
    from specs.catalog.openapi_sync import sync_openapi_for_service
    from specs.payloads.payload_store import ensure_payload_set, get_payload_set

    env = environment or settings.default_environment
    try:
        sync_openapi_for_service(service, env, force=True)
    except Exception:
        pass

    payload_set = ensure_payload_set(service)
    set_version = int(payload_set.get("version") or 0)
    stored_apis = payload_set.get("apis") if isinstance(payload_set.get("apis"), dict) else {}

    apis_data = load_service_apis(service, env)
    apis = list(apis_data.get("apis") or [])

    def _mutation_rank(api_row: dict[str, Any]) -> tuple[int, str, str]:
        """Run create/read first; pause/resume before cancel/delete so state stays usable."""
        p = str(api_row.get("path") or api_row.get("path_template") or "").lower()
        m = str(api_row.get("method") or "GET").upper()
        rank = 0
        if m in ("GET", "HEAD", "OPTIONS"):
            rank = 0
        elif "pause" in p:
            rank = 2
        elif "resume" in p:
            rank = 3
        elif "upgrade" in p or "downgrade" in p:
            rank = 4
        elif "cancel" in p:
            rank = 8
        elif m == "DELETE":
            rank = 9
        elif m == "POST" and p.rstrip("/").endswith("subscriptions"):
            rank = 1  # create early for id harvest
        else:
            rank = 5
        return (rank, p, m)

    apis.sort(key=_mutation_rank)
    results: list[dict[str, Any]] = []
    passed = 0
    failed = 0
    run_ctx: dict[str, Any] = {}

    for api in apis:
        if not isinstance(api, dict):
            continue
        api_id = str(api.get("id") or "")
        method = str(api.get("method") or "GET").upper()
        path = str(api.get("path") or api.get("path_template") or "")
        row_base = {
            "api_id": api_id,
            "method": method,
            "path": path,
            "name": api.get("name"),
        }

        if not try_each:
            results.append({**row_base, "ok": False, "skipped": True, "reason": "try_each_false"})
            failed += 1
            continue

        initial_req: dict[str, Any] | None = None
        initial_source: str | None = None
        if prefer_stored and api_id and isinstance(stored_apis.get(api_id), dict):
            entry = stored_apis[api_id]
            req = entry.get("request") if isinstance(entry.get("request"), dict) else None
            if req and req.get("method"):
                initial_req = {
                    **req,
                    "api_id": api_id,
                    "method": str(req.get("method") or method).upper(),
                    "path": req.get("path") or path,
                }
                initial_source = "set"

        # Prefer ids harvested earlier in this run over stale set/schema examples
        if initial_req is not None and run_ctx:
            initial_req = _apply_run_context(initial_req, run_ctx)

        out = await ensure_working_payload(
            service=service,
            environment=env,
            method=method,
            path=path,
            api_id=api_id or None,
            write_back=write_back,
            allow_llm=allow_llm,
            max_attempts=max_attempts,
            prefer_stored=prefer_stored,
            initial_request=initial_req,
            initial_source=initial_source,
        )
        # If schema/set failed but we now have ids, one more try with run context
        if (
            not out.get("ok")
            and run_ctx
            and "{" in path
            and isinstance(out.get("request"), dict)
        ):
            seeded = _apply_run_context(dict(out["request"]), run_ctx)
            if seeded.get("path_params") != (out.get("request") or {}).get("path_params"):
                out = await ensure_working_payload(
                    service=service,
                    environment=env,
                    method=method,
                    path=path,
                    api_id=api_id or None,
                    write_back=write_back,
                    allow_llm=allow_llm,
                    max_attempts=max_attempts,
                    prefer_stored=False,
                    initial_request=seeded,
                    initial_source="run-context",
                )
        ok = bool(out.get("ok"))
        if ok:
            passed += 1
            resp = out.get("response") if isinstance(out.get("response"), dict) else {}
            body = resp.get("body") if isinstance(resp, dict) else None
            if body is None:
                try_block = out.get("try") if isinstance(out.get("try"), dict) else {}
                body = try_block.get("body")
            run_ctx.update(_harvest_ids_from_body(body))
        else:
            failed += 1
        ps = out.get("payload_set") if isinstance(out.get("payload_set"), dict) else {}
        if ps.get("version") is not None:
            set_version = int(ps["version"])
        # Refresh stored map after writes so later ops see updates if needed
        if ok and write_back:
            fresh = get_payload_set(service, None)
            if fresh and isinstance(fresh.get("apis"), dict):
                stored_apis = fresh["apis"]

        results.append(
            {
                **row_base,
                "ok": ok,
                "final_status": out.get("final_status") or (out.get("try") or {}).get("status_code"),
                "source": out.get("source"),
                "attempts_used": out.get("attempts_used") or len(out.get("attempts") or []),
                "attempts": out.get("attempts") or [],
                "request": out.get("request"),
                "response": out.get("response"),
                "error": out.get("error"),
                "payload_set_version": set_version,
                "llm_attempted": out.get("llm_attempted"),
            }
        )

    # Touch openapi meta for UI chips
    meta = load_openapi_document(service, env)
    return {
        "ok": failed == 0,
        "service": service,
        "environment": env,
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "payload_set_version": set_version,
        "operation_count": meta.get("operation_count"),
        "results": results,
    }


def _resolved_path_from_request(request: dict[str, Any]) -> str:
    """Prefer resolved_path; otherwise substitute path_params into the template."""
    resolved = str(request.get("resolved_path") or "").strip()
    if resolved and "{" not in resolved:
        return resolved.lstrip("/")
    path = str(request.get("path") or "").strip()
    pp = request.get("path_params") if isinstance(request.get("path_params"), dict) else {}
    for k, v in pp.items():
        if v is None:
            continue
        path = path.replace("{" + str(k) + "}", str(v))
    return path.lstrip("/")


async def _try_once(service: str, environment: str, request: dict[str, Any]) -> dict[str, Any]:
    path = _resolved_path_from_request(request)
    # Keep request in sync so UI/MCP see the path that was actually called
    if path:
        request["resolved_path"] = "/" + path if not str(request.get("path") or "").startswith("http") else path
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
