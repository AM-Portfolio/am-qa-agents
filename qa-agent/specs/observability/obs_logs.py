"""Fetch platform (Loki) logs by trace_id via tool-agent observe.logs.query."""
from __future__ import annotations

import logging
import os
from typing import Any

LOG = logging.getLogger(__name__)


def _logql_for_trace(trace_id: str, correlation_id: str | None = None) -> str:
    needle = (trace_id or correlation_id or "").strip()
    safe = needle.replace("\\", "\\\\").replace('"', '\\"')
    return f'{{job=~".+"}} |= "{safe}"'


async def fetch_obs_logs(
    *,
    trace_id: str | None = None,
    correlation_id: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    tid = (trace_id or "").strip()
    cid = (correlation_id or "").strip()
    if not tid and not cid:
        return {
            "available": False,
            "reason": "no_trace_id",
            "lines": [],
            "count": 0,
        }
    if os.getenv("QA_AGENT_SKIP_OBSERVE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        return {
            "available": False,
            "reason": "observe_skipped",
            "trace_id": tid or None,
            "correlation_id": cid or None,
            "lines": [],
            "count": 0,
        }

    query = _logql_for_trace(tid or cid, cid or None)
    payload: dict[str, Any] = {
        "query": query,
        "limit": max(1, min(int(limit or 100), 500)),
    }
    if started_at:
        payload["start"] = started_at
    if finished_at:
        payload["end"] = finished_at

    try:
        from adapters.mcp_fallback import a2a_execute
    except Exception as exc:  # noqa: BLE001
        return {
            "available": False,
            "reason": f"import_error:{exc}",
            "trace_id": tid or None,
            "correlation_id": cid or None,
            "lines": [],
            "count": 0,
        }

    try:
        a2a = await a2a_execute(
            capability="observe.logs.query",
            payload=payload,
            timeout=30.0,
            read_only=True,
        )
    except Exception as exc:  # noqa: BLE001
        LOG.warning("obs-logs a2a failed: %s", exc)
        return {
            "available": False,
            "reason": str(exc),
            "trace_id": tid or None,
            "correlation_id": cid or None,
            "lines": [],
            "count": 0,
        }

    if not a2a.get("ok"):
        return {
            "available": False,
            "reason": a2a.get("error") or f"http_{a2a.get('http_status')}",
            "trace_id": tid or None,
            "correlation_id": cid or None,
            "via": a2a.get("via"),
            "lines": [],
            "count": 0,
        }

    data = a2a.get("data") if isinstance(a2a.get("data"), dict) else {}
    lines = _normalize_lines(data)
    return {
        "available": True,
        "trace_id": tid or None,
        "correlation_id": cid or None,
        "query": query,
        "via": a2a.get("via") or "tool_agent",
        "lines": lines,
        "count": len(lines),
        "raw_keys": list(data.keys())[:20] if isinstance(data, dict) else [],
    }


def _normalize_lines(data: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key in ("lines", "entries", "logs", "results", "rows"):
        raw = data.get(key)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if isinstance(item, str):
                out.append({"message": item})
            elif isinstance(item, dict):
                msg = (
                    item.get("message")
                    or item.get("line")
                    or item.get("log")
                    or item.get("text")
                    or str(item.get("value") or "")
                )
                out.append(
                    {
                        "ts": item.get("ts")
                        or item.get("timestamp")
                        or item.get("time"),
                        "message": str(msg)[:4000],
                        "labels": item.get("labels")
                        if isinstance(item.get("labels"), dict)
                        else None,
                    }
                )
        if out:
            return out
    # Grafana-style streams
    streams = data.get("streams") or data.get("data", {}).get("result")
    if isinstance(streams, list):
        for stream in streams:
            if not isinstance(stream, dict):
                continue
            values = stream.get("values") or []
            labels = stream.get("stream") or stream.get("labels")
            for pair in values:
                if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                    out.append(
                        {
                            "ts": pair[0],
                            "message": str(pair[1])[:4000],
                            "labels": labels if isinstance(labels, dict) else None,
                        }
                    )
    return out
