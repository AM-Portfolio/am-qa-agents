"""REST wrappers for OpenAPI tool call / run (Specs MCP tab)."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from specs.api.platform import router
from specs.schemas import OpenapiToolCallRequest, OpenapiToolsRunRequest


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_openapi_tool_call_request_schema():
    body = OpenapiToolCallRequest(name="api_svc_getThing", arguments={"id": "1"})
    assert body.name == "api_svc_getThing"
    assert body.arguments == {"id": "1"}


def test_openapi_tools_run_request_all_flag():
    body = OpenapiToolsRunRequest(all=True, max_tools=5)
    assert body.all is True
    assert body.max_tools == 5


def test_call_route_wraps_call_tool(client: TestClient):
    fake_tools = {
        "tools": [
            {
                "name": "api_demo_list",
                "method": "GET",
                "path": "/items",
                "service": "demo",
            }
        ]
    }
    with (
        patch(
            "specs.api.platform._ensure_openapi_tools_for_service",
            return_value={"environment": "dev", "tools": fake_tools["tools"]},
        ),
        patch(
            "specs.openapi_tools.registry.list_tools",
            return_value=fake_tools,
        ),
        patch(
            "specs.openapi_tools.registry.call_tool",
            return_value={
                "ok": True,
                "status": 200,
                "url": "https://example.test/items",
                "method": "GET",
                "body": {"items": []},
                "service": "demo",
            },
        ) as call_mock,
    ):
        res = client.post(
            "/api/catalog/demo/openapi/tools/call",
            json={"name": "api_demo_list", "environment": "dev", "arguments": {}},
        )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["tool"] == "api_demo_list"
    assert data["status"] == 200
    assert data["arguments_used"] == {}
    assert "body" in data
    call_mock.assert_called_once()


def test_run_route_batch(client: TestClient):
    fake_tools = {
        "tools": [
            {"name": "t1", "method": "GET", "path": "/a", "service": "demo"},
            {"name": "t2", "method": "GET", "path": "/b", "service": "demo"},
        ]
    }

    def _call(name, arguments=None, **kwargs):
        return {
            "ok": name == "t1",
            "status": 200 if name == "t1" else 500,
            "url": f"https://example.test/{name}",
            "method": "GET",
            "body": {"tool": name},
            "error": None if name == "t1" else "boom",
        }

    with (
        patch(
            "specs.api.platform._ensure_openapi_tools_for_service",
            return_value={"environment": "dev"},
        ),
        patch(
            "specs.openapi_tools.registry.list_tools",
            return_value=fake_tools,
        ),
        patch(
            "specs.openapi_tools.registry.call_tool",
            side_effect=_call,
        ),
    ):
        res = client.post(
            "/api/catalog/demo/openapi/tools/run",
            json={"all": True, "environment": "dev"},
        )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert data["passed"] == 1
    assert data["failed"] == 1
    assert len(data["results"]) == 2
    assert data["results"][0]["tool"] == "t1"
