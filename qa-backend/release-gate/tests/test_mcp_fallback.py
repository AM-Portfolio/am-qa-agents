"""Unit tests for mcp_fallback helpers (no live network)."""

from __future__ import annotations

import json as json_mod

import httpx
import pytest

from am_qa_agent.adapters import mcp_fallback as mf


@pytest.mark.asyncio
async def test_a2a_execute_posts_tools_execute(monkeypatch):
    calls: list[tuple[str, dict]] = []

    class _Resp:
        status_code = 200

        def json(self):
            return {
                "request_id": "r1",
                "backend": "observe",
                "operation": "metrics.query",
                "data": {"ok": True, "capability": "observe.metrics.query", "data": {"kind": "metrics"}},
            }

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def post(self, url, headers=None, json=None):
            calls.append((url, json or {}))
            return _Resp()

    monkeypatch.setattr(mf.httpx, "AsyncClient", _Client)
    out = await mf.a2a_execute(
        capability="observe.metrics.query",
        payload={"services": ["analysis"]},
        base_url="http://tool.test",
    )
    assert out["ok"] is True
    assert out["capability"] == "observe.metrics.query"
    assert calls and calls[0][0].endswith("/api/v1/tools/execute")
    intent = calls[0][1]["intent"]
    assert intent["backend"] == "observe"
    assert intent["operation"] == "metrics.query"
    assert intent["params"]["services"] == ["analysis"]
    assert out["data"]["ok"] is True


@pytest.mark.asyncio
async def test_a2a_execute_rejects_undotted_capability():
    out = await mf.a2a_execute(capability="spt", payload={})
    assert out["ok"] is False
    assert "backend.operation" in (out.get("error") or "")


@pytest.mark.asyncio
async def test_gnx_mcp_sends_accept_header(monkeypatch):
    seen: list[dict] = []

    class _Resp:
        def __init__(self, status, text="", headers=None):
            self.status_code = status
            self.text = text
            self.headers = headers or {}

        def json(self):
            return json.loads(self.text)

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def post(self, url, headers=None, json=None):  # noqa: A002
            seen.append(dict(headers or {}))
            body = json or {}
            method = body.get("method")
            if method == "initialize":
                return _Resp(
                    200,
                    'event: message\ndata: {"result":{},"jsonrpc":"2.0","id":1}\n\n',
                    headers={"mcp-session-id": "sess-1"},
                )
            if method == "notifications/initialized":
                return _Resp(202, "")
            payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "result": {"content": [{"type": "text", "text": "hit"}]},
            }
            return _Resp(200, "data: " + json_mod.dumps(payload) + "\n\n")

    monkeypatch.setattr(mf.httpx, "AsyncClient", _Client)
    out = await mf.gnx_mcp_call(
        tool="query",
        arguments={"search_query": "x", "repo": "am-core-services"},
        base_url="https://gnx.test",
    )
    assert out["ok"] is True
    assert any("application/json, text/event-stream" in (h.get("Accept") or "") for h in seen)
    assert "hit" in mf._mcp_text(out)
