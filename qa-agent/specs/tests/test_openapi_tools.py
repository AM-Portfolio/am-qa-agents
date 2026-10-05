"""OpenAPI tool generation + scenario resolution."""
from __future__ import annotations

from specs.openapi_tools.generator import spec_to_tools
from ui_evidence.api.auth_identity_profiles import resolve_tool_for_scenario


def test_spec_to_tools_basic():
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "t", "version": "1"},
        "paths": {
            "/auth/login": {
                "post": {
                    "operationId": "login",
                    "summary": "Login",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "username": {"type": "string"},
                                        "password": {"type": "string"},
                                    },
                                    "required": ["username", "password"],
                                }
                            }
                        }
                    },
                }
            },
            "/users/me": {
                "get": {
                    "operationId": "usersMe",
                    "summary": "Me",
                }
            },
            "/items/{id}": {
                "delete": {
                    "operationId": "deleteItem",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                }
            },
        },
    }
    tools = spec_to_tools(spec, base_url="https://am.asrax.in/identity", service="am-identity")
    names = {t["_meta"]["tool_name"] for t in tools}
    assert any("login" in n for n in names)
    assert any("usersMe" in n or "users_me" in n.lower() for n in names)
    # delete skipped by default
    assert not any("delete" in n.lower() for n in names)


def test_resolve_tool_for_login_scenario():
    tools = [
        {
            "name": "api_am_identity_login",
            "method": "post",
            "path": "/auth/login",
            "op_id": "login",
        },
        {
            "name": "api_am_identity_usersMe",
            "method": "get",
            "path": "/users/me",
            "op_id": "usersMe",
        },
    ]
    hit = resolve_tool_for_scenario(
        tools,
        {
            "path_contains": "/auth/login",
            "method": "post",
            "tool_match": ["login"],
        },
    )
    assert hit is not None
    assert hit["path"] == "/auth/login"
