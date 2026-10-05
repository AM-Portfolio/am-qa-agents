"""OpenAPI → tool schemas + HTTP executor (fin-agent pattern, no extra deps)."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _resolve_ref(ref: str, spec: dict[str, Any]) -> dict[str, Any]:
    parts = ref.lstrip("#/").split("/")
    node: Any = spec
    for p in parts:
        node = node.get(p, {}) if isinstance(node, dict) else {}
    return node if isinstance(node, dict) else {}


def _schema_to_properties(
    schema: dict[str, Any], spec: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    if not schema:
        return {}, []
    if "$ref" in schema:
        schema = _resolve_ref(str(schema["$ref"]), spec)
    merged: dict[str, Any] = {}
    required: list[str] = list(schema.get("required") or [])
    for combiner in ("allOf", "oneOf", "anyOf"):
        for sub in schema.get(combiner) or []:
            if not isinstance(sub, dict):
                continue
            resolved = sub if "$ref" not in sub else _resolve_ref(str(sub["$ref"]), spec)
            props, reqs = _schema_to_properties(resolved, spec)
            merged.update(props)
            required.extend(reqs)
    for name, prop_schema in (schema.get("properties") or {}).items():
        if not isinstance(prop_schema, dict):
            continue
        if "$ref" in prop_schema:
            prop_schema = _resolve_ref(str(prop_schema["$ref"]), spec)
        merged[str(name)] = {
            "type": prop_schema.get("type", "string"),
            "description": prop_schema.get("description", name),
        }
        if "enum" in prop_schema:
            merged[str(name)]["enum"] = prop_schema["enum"]
    return merged, list(set(required))


def _derive_op_id(method: str, path: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9]", "_", path).strip("_")
    return f"{method}_{safe}"


def _tool_name(service: str, op_id: str) -> str:
    raw = f"api_{service}_{op_id}"
    return re.sub(r"[^a-zA-Z0-9_]", "_", raw)[:96]


def spec_to_tools(
    spec_dict: dict[str, Any],
    *,
    base_url: str = "",
    service: str = "",
    skip_delete: bool = True,
) -> list[dict[str, Any]]:
    """Convert OpenAPI dict → tool list with private _meta routing."""
    tools: list[dict[str, Any]] = []
    if not base_url:
        servers = spec_dict.get("servers") or []
        if servers and isinstance(servers[0], dict):
            base_url = str(servers[0].get("url") or "")
    base_url = base_url.rstrip("/")
    paths = spec_dict.get("paths") or {}
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete"):
            operation = path_item.get(method)
            if not operation or not isinstance(operation, dict):
                continue
            if skip_delete and method == "delete":
                continue
            op_id = str(operation.get("operationId") or _derive_op_id(method, str(path)))
            summary = (
                operation.get("summary") or operation.get("description") or op_id
            )
            properties: dict[str, Any] = {}
            required: list[str] = []
            for param in operation.get("parameters") or []:
                if not isinstance(param, dict):
                    continue
                if "$ref" in param:
                    param = _resolve_ref(str(param["$ref"]), spec_dict)
                p_name = str(param.get("name") or "")
                if not p_name:
                    continue
                p_schema = param.get("schema") or {}
                if isinstance(p_schema, dict) and "$ref" in p_schema:
                    p_schema = _resolve_ref(str(p_schema["$ref"]), spec_dict)
                if not isinstance(p_schema, dict):
                    p_schema = {}
                properties[p_name] = {
                    "type": p_schema.get("type", "string"),
                    "description": param.get("description", p_name),
                }
                if param.get("required"):
                    required.append(p_name)
            body = operation.get("requestBody") or {}
            if isinstance(body, dict) and body:
                content = body.get("content") or {}
                json_content = content.get("application/json") or {}
                body_schema = json_content.get("schema") or {}
                if isinstance(body_schema, dict) and "$ref" in body_schema:
                    body_schema = _resolve_ref(str(body_schema["$ref"]), spec_dict)
                if isinstance(body_schema, dict):
                    props, reqs = _schema_to_properties(body_schema, spec_dict)
                    properties.update(props)
                    required.extend(reqs)
            name = _tool_name(service or "svc", op_id)
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": f"[{service}] {summary}" if service else str(summary),
                        "parameters": {
                            "type": "object",
                            "properties": properties,
                            "required": list(set(required)),
                        },
                    },
                    "_meta": {
                        "method": method,
                        "path": path,
                        "base_url": base_url,
                        "op_id": op_id,
                        "service": service,
                        "tool_name": name,
                    },
                }
            )
    logger.info(
        "spec_to_tools: service=%s tools=%s base=%s",
        service,
        len(tools),
        base_url,
    )
    return tools


def execute_openapi_tool_sync(
    meta: dict[str, Any],
    args: dict[str, Any] | None = None,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Execute one OpenAPI tool call synchronously."""
    args = dict(args or {})
    method = str(meta.get("method") or "get").upper()
    path = str(meta.get("path") or "/")
    base_url = str(meta.get("base_url") or "").rstrip("/")
    path_param_names = set(re.findall(r"\{(\w+)\}", path))
    for key in path_param_names:
        if key in args:
            path = path.replace(f"{{{key}}}", str(args[key]))
    url = base_url + path
    remaining = {k: v for k, v in args.items() if k not in path_param_names}
    req_headers = dict(headers or {})
    try:
        with httpx.Client(timeout=timeout) as client:
            if method in ("GET", "DELETE", "HEAD"):
                resp = client.request(method, url, params=remaining or None, headers=req_headers)
            else:
                resp = client.request(method, url, json=remaining or None, headers=req_headers)
        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                body: Any = resp.json()
            except Exception:  # noqa: BLE001
                body = resp.text
        else:
            body = resp.text[:8000]
        return {
            "status": resp.status_code,
            "ok": 200 <= resp.status_code < 400,
            "url": url,
            "method": method,
            "body": body,
            "service": meta.get("service"),
            "op_id": meta.get("op_id"),
            "tool_name": meta.get("tool_name"),
        }
    except httpx.TimeoutException:
        return {"status": 504, "ok": False, "error": f"timeout {url}", "url": url}
    except Exception as exc:  # noqa: BLE001
        logger.error("execute_openapi_tool failed %s %s: %s", method, url, exc)
        return {"status": 500, "ok": False, "error": str(exc), "url": url}


def execute_openapi_tool_json(
    meta: dict[str, Any], args: dict[str, Any] | None = None, **kwargs: Any
) -> str:
    return json.dumps(execute_openapi_tool_sync(meta, args, **kwargs), default=str)
