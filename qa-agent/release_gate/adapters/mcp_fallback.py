"""Shared MCP / tool-agent fallback helpers for qa-agent specialists.

Real specialists first; when they are down or incomplete, call tool-agent
(`/api/v1/tools/execute|query`) or GitNexus MCP HTTP (`/api/mcp`) and record
an honest `mode`:

  live | observe | litellm | fallback_mcp | fallback_gnx | fallback_template | skipped

Replace each fallback with the real specialist once Vault/LLM/Grafana are ready.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

MODE_LIVE = "live"
MODE_OBSERVE = "observe"
MODE_FALLBACK_MCP = "fallback_mcp"
MODE_FALLBACK_GNX = "fallback_gnx"
MODE_FALLBACK_TEMPLATE = "fallback_template"
MODE_SKIPPED = "skipped"

_MCP_ACCEPT = "application/json, text/event-stream"


def tool_agent_base(explicit: str | None = None) -> str:
    return (
        explicit
        or os.getenv("TOOL_AGENT_BASE_URL")
        or os.getenv("TOOL_AGENT_URL")
        or "http://127.0.0.1:8141"
    ).rstrip("/")


def gnx_mcp_base(explicit: str | None = None) -> str:
    """Return GNX MCP base URL, or empty when GitNexus is disabled/unset."""
    raw = (explicit if explicit is not None else os.getenv("GNX_MCP_URL")) or ""
    return raw.strip().rstrip("/")


def _split_capability(capability: str) -> tuple[str, str]:
    """Map `observe.metrics.query` → backend `observe`, operation `metrics.query`."""
    raw = (capability or "").strip()
    if "." not in raw:
        raise ValueError(f"capability must be backend.operation, got {capability!r}")
    backend, operation = raw.split(".", 1)
    if not backend or not operation:
        raise ValueError(f"invalid capability {capability!r}")
    return backend, operation


def _caller_headers() -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Agent-Caller": os.getenv("QA_AGENT_CALLER", "qa-agent"),
    }


async def a2a_execute(
    *,
    capability: str,
    payload: dict[str, Any],
    base_url: str | None = None,
    op: str = "execute",
    timeout: float = 45.0,
    read_only: bool = True,
) -> dict[str, Any]:
    """POST tool-agent `/api/v1/tools/execute` (IntentDocument).

    `op` is retained for call-site compatibility; operation comes from capability.
    """
    _ = op  # legacy kw; capability encodes backend.operation
    base = tool_agent_base(base_url)
    try:
        backend, operation = _split_capability(capability)
    except ValueError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "via": "tool_agent_execute",
            "capability": capability,
            "base_url": base,
        }

    intent = {
        "backend": backend,
        "operation": operation,
        "params": payload or {},
        "read_only": read_only,
        "confidence": 1.0,
        "rationale": "qa-agent mcp fallback",
    }
    body = {"intent": intent, "include_summary": True, "max_rows": 100}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{base}/api/v1/tools/execute",
                headers=_caller_headers(),
                json=body,
            )
            data: Any
            try:
                data = resp.json()
            except Exception:  # noqa: BLE001
                data = {"text": resp.text[:800]}
            nested = data.get("data") if isinstance(data, dict) else None
            # Prefer domain envelope when present
            domain = nested if isinstance(nested, dict) else data
            return {
                "ok": resp.status_code < 400,
                "http_status": resp.status_code,
                "data": domain if isinstance(domain, dict) else {"value": domain},
                "raw": data if isinstance(data, dict) else {"body": data},
                "via": "tool_agent_execute",
                "capability": capability,
                "base_url": base,
            }
    except httpx.HTTPError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "via": "tool_agent_execute",
            "capability": capability,
            "base_url": base,
        }


async def tools_query(
    *,
    query: str,
    backend: str | None = None,
    base_url: str | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """POST tool-agent `/api/v1/tools/query` — NL fallback when structured ops fail."""
    base = tool_agent_base(base_url)
    body: dict[str, Any] = {
        "query": query,
        "read_only": True,
        "include_summary": True,
        "max_rows": 50,
    }
    if backend:
        body["backend"] = backend
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{base}/api/v1/tools/query",
                headers=_caller_headers(),
                json=body,
            )
            try:
                data = resp.json()
            except Exception:  # noqa: BLE001
                data = {"text": resp.text[:800]}
            nested = data.get("data") if isinstance(data, dict) else None
            domain = nested if isinstance(nested, dict) else data
            return {
                "ok": resp.status_code < 400,
                "http_status": resp.status_code,
                "data": domain if isinstance(domain, dict) else {"value": domain},
                "raw": data if isinstance(data, dict) else {"body": data},
                "via": "tool_agent_query",
                "base_url": base,
            }
    except httpx.HTTPError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "via": "tool_agent_query",
            "base_url": base,
        }


async def gnx_mcp_call(
    *,
    tool: str,
    arguments: dict[str, Any],
    base_url: str | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """JSON-RPC tools/call against GitNexus MCP HTTP (`/api/mcp`)."""
    base = gnx_mcp_base(base_url)
    if not base:
        return {
            "ok": False,
            "error": "gnx_disabled",
            "via": "gnx_mcp",
            "skipped": True,
        }
    mcp_url = f"{base}/api/mcp"
    headers = {
        "Accept": _MCP_ACCEPT,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            init = await client.post(
                mcp_url,
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "qa-agent", "version": "0.1.0"},
                    },
                },
            )
            sid = init.headers.get("mcp-session-id") or init.headers.get("Mcp-Session-Id")
            sess = {**headers}
            if sid:
                sess["Mcp-Session-Id"] = sid
                await client.post(
                    mcp_url,
                    headers=sess,
                    json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                )
            call = await client.post(
                mcp_url,
                headers=sess,
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": tool, "arguments": arguments},
                },
            )
            text = call.text
            parsed: Any = None
            if "data: " in text:
                lines = [ln[6:] for ln in text.splitlines() if ln.startswith("data: ")]
                if lines:
                    try:
                        parsed = json.loads(lines[-1])
                    except json.JSONDecodeError:
                        parsed = {"raw": lines[-1][:2000]}
            else:
                try:
                    parsed = call.json()
                except Exception:  # noqa: BLE001
                    parsed = {"raw": text[:2000]}
            # JSON-RPC error → not ok even if HTTP 200
            rpc_err = isinstance(parsed, dict) and parsed.get("error")
            return {
                "ok": call.status_code < 400 and not rpc_err,
                "http_status": call.status_code,
                "data": parsed,
                "error": (rpc_err.get("message") if isinstance(rpc_err, dict) else None),
                "via": "gnx_mcp",
                "tool": tool,
                "base_url": base,
            }
    except httpx.HTTPError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "via": "gnx_mcp",
            "tool": tool,
            "base_url": base,
        }


def _mcp_text(result: dict[str, Any]) -> str:
    data = result.get("data")
    if not isinstance(data, dict):
        return str(data or "")[:4000]
    # tools/call result shapes
    content = ((data.get("result") or {}).get("content")) if "result" in data else None
    if isinstance(content, list) and content:
        parts = [str(c.get("text") or "") for c in content if isinstance(c, dict)]
        return "\n".join(parts)[:4000]
    return json.dumps(data, ensure_ascii=False)[:4000]
