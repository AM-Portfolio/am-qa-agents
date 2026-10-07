"""Load prod Swagger for catalog services and keep generated MCP tool registry."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from specs.catalog.catalog_loader import (
    _platform_openapi_headers,
    list_registered_services,
    load_service_apis,
    reachable_target_for_service,
)
from specs.catalog.openapi_import import (
    default_openapi_path,
    fetch_openapi_sync,
    openapi_url,
)
from specs.config import settings
from specs.openapi_tools.generator import execute_openapi_tool_sync, spec_to_tools

logger = logging.getLogger(__name__)

_TOOLS: dict[str, dict[str, Any]] = {}
_LAST_REFRESH: dict[str, Any] = {}


def _cache_path() -> Path:
    return Path(settings.data_dir) / "openapi_tools" / "registry.json"


def _persist() -> None:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "tools": {
            name: {
                "function": t.get("function"),
                "_meta": t.get("_meta"),
            }
            for name, t in _TOOLS.items()
        },
        "last_refresh": _LAST_REFRESH,
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _load_cache() -> None:
    global _TOOLS, _LAST_REFRESH
    path = _cache_path()
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return
    tools = data.get("tools") if isinstance(data, dict) else None
    if not isinstance(tools, dict):
        return
    loaded: dict[str, dict[str, Any]] = {}
    for name, row in tools.items():
        if not isinstance(row, dict):
            continue
        loaded[str(name)] = {
            "type": "function",
            "function": row.get("function") or {},
            "_meta": row.get("_meta") or {},
        }
    _TOOLS = loaded
    _LAST_REFRESH = data.get("last_refresh") if isinstance(data.get("last_refresh"), dict) else {}


def list_tools(
    *,
    service: str | None = None,
    q: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    if not _TOOLS:
        _load_cache()
    rows: list[dict[str, Any]] = []
    qn = (q or "").strip().lower()
    for name, tool in sorted(_TOOLS.items()):
        meta = tool.get("_meta") or {}
        if service and str(meta.get("service") or "") != service:
            continue
        fn = tool.get("function") or {}
        desc = str(fn.get("description") or "")
        if qn and qn not in name.lower() and qn not in desc.lower():
            continue
        rows.append(
            {
                "name": name,
                "description": desc,
                "service": meta.get("service"),
                "method": meta.get("method"),
                "path": meta.get("path"),
                "op_id": meta.get("op_id"),
            }
        )
        if len(rows) >= max(1, int(limit)):
            break
    return {
        "count": len(rows),
        "total_cached": len(_TOOLS),
        "last_refresh": _LAST_REFRESH,
        "tools": rows,
    }


def _fetch_spec_for_service(service: str, environment: str) -> tuple[dict[str, Any] | None, str, str | None]:
    """Return (spec, base_url, error)."""
    target = reachable_target_for_service(service, environment) or ""
    if not target or target == "https://am.asrax.in":
        # Prefer registration prod target via load_service_apis side effects
        data = load_service_apis(service, environment)
        target = str(data.get("target_url") or target or "")
    if not target:
        return None, "", f"no target for {service}/{environment}"

    from specs.catalog.catalog_loader import load_registration

    reg = load_registration(service) or {}
    runtime = str(reg.get("runtime") or "python")
    oas = reg.get("openapi") if isinstance(reg.get("openapi"), dict) else {}
    preferred = str(oas.get("path") or default_openapi_path(runtime))
    headers = _platform_openapi_headers(environment=environment)
    headers.setdefault("Accept", "application/json")
    last_err: str | None = None
    for path in (preferred, "/openapi.json", "/v3/api-docs", "/api-docs"):
        url = openapi_url(target, path)
        try:
            doc = fetch_openapi_sync(url, headers=headers, timeout=20.0)
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            continue
        if isinstance(doc, dict) and doc.get("paths"):
            return doc, target.rstrip("/"), None
        last_err = f"empty or non-OpenAPI at {url}"
    return None, target.rstrip("/"), last_err or "openapi fetch failed"


def tools_from_openapi_document(
    doc: dict[str, Any],
    *,
    service: str,
    base_url: str = "",
    environment: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Build slim Specs MCP tool rows from the same OpenAPI doc as Swagger/APIs."""
    from specs.catalog.openapi_import import _slug, count_openapi_operations

    global _TOOLS, _LAST_REFRESH
    tools = spec_to_tools(
        doc,
        base_url=base_url,
        service=service,
        skip_delete=False,
    )
    env = (environment or settings.default_environment or "dev").strip()
    for t in tools:
        meta = t.setdefault("_meta", {})
        meta["environment"] = env
    if persist:
        if not _TOOLS:
            _load_cache()
        _TOOLS = {
            k: v
            for k, v in _TOOLS.items()
            if str((v.get("_meta") or {}).get("service") or "") != service
        }
        for t in tools:
            name = str((t.get("_meta") or {}).get("tool_name") or "")
            if name:
                _TOOLS[name] = t
        _LAST_REFRESH = {
            **(_LAST_REFRESH or {}),
            "last_service": service,
            "last_service_tools": len(tools),
        }
        _persist()

    rows: list[dict[str, Any]] = []
    for t in tools:
        meta = t.get("_meta") or {}
        fn = t.get("function") or {}
        op_id = str(meta.get("op_id") or "")
        rows.append(
            {
                "name": meta.get("tool_name") or fn.get("name"),
                "method": str(meta.get("method") or "").upper(),
                "path": meta.get("path"),
                "op_id": op_id,
                "description": fn.get("description") or "",
                "api_id": _slug(op_id),
            }
        )
    return {
        "tools": rows,
        "count": len(rows),
        "operation_count": count_openapi_operations(doc),
    }


def refresh_tools_from_prod(
    *,
    environment: str | None = None,
    services: list[str] | None = None,
) -> dict[str, Any]:
    """Fetch prod (or env) Swagger for catalog services and rebuild tool registry."""
    global _TOOLS, _LAST_REFRESH
    env = environment or settings.default_environment or "prod"
    svc_rows = list_registered_services()
    service_ids = [str(s.get("id") or s.get("service") or "") for s in svc_rows]
    service_ids = [s for s in service_ids if s]
    if services:
        wanted = set(services)
        service_ids = [s for s in service_ids if s in wanted] or list(services)

    new_tools: dict[str, dict[str, Any]] = {}
    per_service: list[dict[str, Any]] = []
    for sid in service_ids:
        spec, base, err = _fetch_spec_for_service(sid, env)
        if not spec:
            per_service.append(
                {"service": sid, "ok": False, "error": err, "tools": 0, "target": base}
            )
            continue
        tools = spec_to_tools(spec, base_url=base, service=sid, skip_delete=False)
        for t in tools:
            meta = t.setdefault("_meta", {})
            meta["environment"] = env
            name = str(meta.get("tool_name") or "")
            if name:
                new_tools[name] = t
        try:
            from specs.catalog.openapi_import import openapi_to_apis
            from specs.catalog.openapi_sync import save_synced_openapi

            save_synced_openapi(
                sid,
                env,
                document=spec,
                openapi_url=openapi_url(base, default_openapi_path("python")) if base else "",
                target_url=base or "",
                apis=openapi_to_apis(spec, include_mutating=True),
            )
        except Exception as sync_exc:  # noqa: BLE001
            logger.info("openapi sync from tools refresh skipped for %s: %s", sid, sync_exc)
        per_service.append(
            {
                "service": sid,
                "ok": True,
                "tools": len(tools),
                "target": base,
                "paths": len(spec.get("paths") or {}),
            }
        )

    _TOOLS = new_tools
    _LAST_REFRESH = {
        "environment": env,
        "services": len(service_ids),
        "tools": len(new_tools),
        "per_service": per_service,
    }
    _persist()
    return {
        "ok": True,
        "environment": env,
        "tool_count": len(new_tools),
        "services": per_service,
    }


def call_tool(
    name: str,
    arguments: dict[str, Any] | None = None,
    *,
    with_identity_auth: bool = True,
    record_run: bool = True,
    environment: str | None = None,
) -> dict[str, Any]:
    """Invoke a generated tool; optionally attach identity JWT and persist a Specs run."""
    if not _TOOLS:
        _load_cache()
    tool = _TOOLS.get(name)
    if not tool:
        return {"ok": False, "error": f"unknown tool: {name}", "hint": "spt_refresh_openapi_tools"}
    meta = dict(tool.get("_meta") or {})
    env = (
        (environment or "").strip()
        or str(meta.get("environment") or "").strip()
        or settings.default_environment
        or "dev"
    )
    meta["environment"] = env
    headers: dict[str, str] = {"Accept": "application/json"}
    if with_identity_auth:
        try:
            auth = _platform_openapi_headers(environment=env)
            if auth.get("Authorization"):
                headers["Authorization"] = auth["Authorization"]
        except Exception as exc:  # noqa: BLE001
            logger.warning("identity auth for tool call failed: %s", exc)
    result = execute_openapi_tool_sync(meta, arguments, headers=headers)
    if record_run:
        try:
            _record_tool_run(name, meta, arguments or {}, result)
        except Exception as exc:  # noqa: BLE001
            logger.warning("record tool run failed: %s", exc)
            result["record_error"] = str(exc)
    return result


def _record_tool_run(
    name: str,
    meta: dict[str, Any],
    arguments: dict[str, Any],
    result: dict[str, Any],
) -> str | None:
    from datetime import datetime, timezone

    from specs.persistence.run_store import save_run
    from specs.persistence.trace_store import save_api_index, save_traces_file

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = f"openapi-tool-{name}"[:100]
    ok = bool(result.get("ok"))
    status_code = int(result.get("status") or 0)
    trace = {
        "kind": "http",
        "call_index": 1,
        "api_id": name,
        "name": name,
        "method": str(meta.get("method") or "").upper(),
        "path": meta.get("path"),
        "url": result.get("url"),
        "vu": 1,
        "iter": 0,
        "request": {"headers": {}, "body": json.dumps(arguments, default=str)},
        "response": {
            "status": status_code,
            "headers": {},
            "body": json.dumps(result.get("body"), default=str)[:20000],
        },
        "timings": {},
        "checks_passed": ok,
    }
    index = [
        {
            "api_id": name,
            "name": name,
            "method": trace["method"],
            "path": meta.get("path"),
            "trace_available": True,
            "checks_passed": ok,
            "request_count": 1,
            "pass_count": 1 if ok else 0,
            "fail_count": 0 if ok else 1,
            "status": "done",
            "kind": "http",
            "http_status": status_code,
        }
    ]
    art = Path(settings.data_dir) / "artifacts" / run_id
    art.mkdir(parents=True, exist_ok=True)
    save_traces_file(art / "traces.json", [trace])
    save_api_index(art / "api-index.json", index)
    save_run(
        {
            "id": run_id,
            "started_at": now,
            "finished_at": now,
            "status": "passed" if ok else "failed",
            "passed": ok,
            "runner": "openapi-tool",
            "run_profile": "api",
            "config_name": name,
            "service": meta.get("service") or "platform",
            "environment": settings.default_environment or "prod",
            "test_type": "k6",
            "audience": "agent",
            "triggered_by": "spt_call_openapi_tool",
            "target_url": result.get("url"),
            "api_summary": index,
            "api_count": 1,
            "api_pass_count": 1 if ok else 0,
            "api_fail_count": 0 if ok else 1,
            "error": None if ok else str(result.get("error") or status_code),
        }
    )
    return run_id
