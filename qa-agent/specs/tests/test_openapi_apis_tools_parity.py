"""Specs APIs list ↔ Swagger ops ↔ MCP tools count parity."""
from __future__ import annotations

from specs.catalog.openapi_import import count_openapi_operations, openapi_to_apis
from specs.openapi_tools.generator import spec_to_tools
from specs.openapi_tools.registry import tools_from_openapi_document


def _fixture_doc() -> dict:
    return {
        "openapi": "3.0.0",
        "info": {"title": "sub", "version": "0.1.0"},
        "paths": {
            "/health": {
                "get": {
                    "operationId": "health",
                    "summary": "Health",
                }
            },
            "/subscriptions/plans": {
                "get": {
                    "operationId": "listPlans",
                    "summary": "List Plans",
                }
            },
            "/subscriptions": {
                "post": {
                    "operationId": "createSubscription",
                    "summary": "Create",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"plan_id": {"type": "string"}},
                                }
                            }
                        }
                    },
                }
            },
            "/subscriptions/{subscription_id}/cancel": {
                "patch": {
                    "operationId": "cancelSubscription",
                    "summary": "Cancel",
                    "parameters": [
                        {
                            "name": "subscription_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                }
            },
            "/subscriptions/{subscription_id}/delete": {
                "delete": {
                    "operationId": "deleteSubscription",
                    "parameters": [
                        {
                            "name": "subscription_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                }
            },
            "/items": {
                "get": {
                    "operationId": "listItems",
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                }
            },
        },
    }


def test_openapi_to_apis_includes_mutating_and_unresolved():
    doc = _fixture_doc()
    apis = openapi_to_apis(doc, include_mutating=True)
    methods = {(a["method"], a["path"]) for a in apis}
    assert ("POST", "/subscriptions") in methods
    assert ("PATCH", "/subscriptions/{subscription_id}/cancel") in methods
    assert ("DELETE", "/subscriptions/{subscription_id}/delete") in methods
    cancel = next(a for a in apis if a["method"] == "PATCH")
    assert cancel.get("needs_params") is True
    assert cancel.get("path_template") == "/subscriptions/{subscription_id}/cancel"
    list_items = next(a for a in apis if a["id"] == "listitems" or "listItems" in a.get("operation_id", ""))
    assert list_items.get("needs_params") is True
    assert count_openapi_operations(doc) == len(apis)


def test_apis_tools_operation_count_parity():
    doc = _fixture_doc()
    ops = count_openapi_operations(doc)
    apis = openapi_to_apis(doc, include_mutating=True)
    tools = spec_to_tools(
        doc,
        base_url="https://am-dev.asrax.in",
        service="am-subscription",
        skip_delete=False,
    )
    slim = tools_from_openapi_document(
        doc,
        service="am-subscription",
        base_url="https://am-dev.asrax.in",
        persist=False,
    )
    assert ops == len(apis) == len(tools) == slim["count"] == slim["operation_count"]


def test_get_only_mode_still_available():
    doc = _fixture_doc()
    apis = openapi_to_apis(doc, include_mutating=False)
    assert all(a["method"] in ("GET", "HEAD") for a in apis)
    assert len(apis) < count_openapi_operations(doc)
