"""Convert live OpenAPI documents into SPT catalog API entries."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
import yaml

logger = logging.getLogger(__name__)

_HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")

# Runtime → default OpenAPI path on the live service
OPENAPI_PATH_BY_RUNTIME: dict[str, str] = {
    "java": "/v3/api-docs",
    "python": "/openapi.json",
    "fastapi": "/openapi.json",
    "spring": "/v3/api-docs",
}


def default_openapi_path(runtime: str | None) -> str:
    key = (runtime or "java").strip().lower()
    return OPENAPI_PATH_BY_RUNTIME.get(key, "/v3/api-docs")


def _slug(value: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", ".", value.strip().lower()).strip(".")
    return s or "op"


def _param_example(param: dict[str, Any]) -> str | None:
    if param.get("example") is not None:
        return str(param["example"])
    schema = param.get("schema") or {}
    if schema.get("example") is not None:
        return str(schema["example"])
    if schema.get("default") is not None:
        return str(schema["default"])
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return str(enum[0])
    # Generic pagination only — closed domain codes must come from OpenAPI enum/example
    name = str(param.get("name") or "").lower()
    if name in ("page", "offset"):
        return "0"
    if name in ("size", "limit"):
        return "10"
    return None


def _resolve_path(path: str, parameters: list[dict[str, Any]]) -> str | None:
    """Fill path templates; return None if a required path param has no example."""
    out = path
    for match in re.finditer(r"\{([^}/]+)\}", path):
        name = match.group(1)
        param = next(
            (p for p in parameters if p.get("in") == "path" and p.get("name") == name),
            {"name": name, "required": True},
        )
        example = _param_example(param)
        if example is None:
            return None
        out = out.replace("{" + name + "}", example)
    return out


def _needs_auth(doc: dict[str, Any], op: dict[str, Any], path: str = "") -> bool:
    # Explicit empty security array = public endpoint
    if op.get("security") is not None:
        return bool(op.get("security"))
    if doc.get("security"):
        return True
    for param in op.get("parameters") or []:
        if str(param.get("name") or "").lower() == "authorization":
            return True
    # Spring often puts bearer in components without per-op security
    schemes = ((doc.get("components") or {}).get("securitySchemes")) or {}
    if schemes:
        return True
    # Many platform services omit securitySchemes in /v3/api-docs but still require JWT.
    # Treat health/docs as public; everything else needs auth for load tests.
    pl = str(path or "").lower()
    public_hints = (
        "/actuator/health",
        "/actuator/info",
        "/health",
        "/api-docs",
        "/v3/api-docs",
        "/openapi",
        "/swagger",
    )
    if any(h in pl for h in public_hints):
        return False
    return True


def count_openapi_operations(doc: dict[str, Any]) -> int:
    """Count HTTP operations on paths (same verbs as openapi_to_apis / Specs Swagger)."""
    paths = doc.get("paths") or {}
    total = 0
    for item in paths.values():
        if not isinstance(item, dict):
            continue
        for method in _HTTP_METHODS:
            if isinstance(item.get(method), dict):
                total += 1
    return total


def openapi_to_apis(
    doc: dict[str, Any],
    *,
    include_mutating: bool = True,
) -> list[dict[str, Any]]:
    """Map OpenAPI paths → SPT api rows (all methods by default for Specs sync).

    Unresolved path templates and required query without examples are kept with
    ``needs_params: true`` so the APIs list matches Swagger operation counts.
    """
    paths = doc.get("paths") or {}
    apis: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw_path, item in paths.items():
        if not isinstance(item, dict):
            continue
        shared_params = list(item.get("parameters") or [])
        for method in _HTTP_METHODS:
            op = item.get(method)
            if not isinstance(op, dict):
                continue
            if not include_mutating and method not in ("get", "head"):
                continue
            params = shared_params + list(op.get("parameters") or [])
            resolved = _resolve_path(str(raw_path), params)
            needs_params = resolved is None
            path_out = resolved if resolved is not None else str(raw_path)

            op_id = str(op.get("operationId") or f"{method}.{raw_path}")
            api_id = _slug(op_id)
            if api_id in seen:
                api_id = _slug(f"{method}.{raw_path}")
            seen.add(api_id)

            query: dict[str, str] = {}
            for param in params:
                if param.get("in") != "query":
                    continue
                name = str(param.get("name") or "")
                if not name:
                    continue
                example = _param_example(param)
                if example is not None:
                    query[name] = example
                elif param.get("required"):
                    needs_params = True

            headers: dict[str, str] = {"Accept": "application/json"}
            if _needs_auth(doc, op, str(raw_path)):
                headers["Authorization"] = "{{env.SPT_AUTH_TOKEN}}"

            summary = str(
                op.get("summary") or op.get("operationId") or f"{method.upper()} {path_out}"
            )
            row: dict[str, Any] = {
                "id": api_id,
                "name": summary,
                "method": method.upper(),
                "path": path_out,
                "operation_id": op_id,
                "headers": headers,
                "query": query,
                "body": None,
                "checks": ["status_2xx"],
                "source": "openapi",
            }
            if needs_params:
                row["needs_params"] = True
                row["path_template"] = str(raw_path)
            apis.append(row)

    return apis


def parse_openapi_bytes(raw: bytes, content_type: str = "") -> dict[str, Any]:
    text = raw.decode("utf-8", errors="replace")
    ct = (content_type or "").lower()
    stripped = text.lstrip()
    # Flutter SPA / HTML catch-all often returns 200 for /openapi.json
    if "text/html" in ct or stripped[:15].lower().startswith(("<!doctype", "<html")):
        raise ValueError("response is HTML, not OpenAPI")
    if "yaml" in ct or stripped.startswith(("openapi:", "swagger:")):
        data = yaml.safe_load(text)
    else:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("OpenAPI document is not an object")
    if not (data.get("paths") or data.get("openapi") or data.get("swagger")):
        raise ValueError("document missing OpenAPI markers (paths/openapi/swagger)")
    return data


def fetch_openapi_sync(
    url: str,
    *,
    timeout: float = 20.0,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url, headers=headers or {})
        resp.raise_for_status()
        return parse_openapi_bytes(resp.content, resp.headers.get("content-type", ""))


async def fetch_openapi(
    url: str,
    *,
    timeout: float = 20.0,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers or {})
        resp.raise_for_status()
        return parse_openapi_bytes(resp.content, resp.headers.get("content-type", ""))


def openapi_url(target_url: str, openapi_path: str) -> str:
    path = openapi_path if openapi_path.startswith("/") else f"/{openapi_path}"
    return f"{target_url.rstrip('/')}{path}"
