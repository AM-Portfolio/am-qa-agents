"""generate-all / ensure_working multi-attempt payload prep."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from specs.payloads.payload_pipeline import (
    _resolved_path_from_request,
    ensure_working_payload,
    generate_all_payloads,
)


def test_resolved_path_substitutes_path_params():
    path = _resolved_path_from_request(
        {
            "path": "/subscriptions/{subscription_id}/cancel",
            "path_params": {"subscription_id": "038bb930-ae97-41ae-850e-708580ef4d3a"},
        }
    )
    assert path == "subscriptions/038bb930-ae97-41ae-850e-708580ef4d3a/cancel"
    assert "{" not in path


@pytest.mark.asyncio
async def test_ensure_working_succeeds_on_third_llm_attempt():
    built = {
        "ok": True,
        "source": "schema",
        "operation_key": "create",
        "request": {
            "method": "POST",
            "path": "/subscriptions",
            "api_id": "create.subscription",
            "query": {},
            "path_params": {},
            "body": {"plan_id": "x"},
        },
        "mcp_attempted": False,
        "mcp_fields": [],
    }
    fail = {"status_code": 422, "error": "validation", "body": {"detail": "bad plan"}}
    ok = {"status_code": 200, "error": None, "body": {"id": "1"}}

    with (
        patch("specs.payloads.payload_pipeline.build_payload", return_value=built),
        patch(
            "specs.payloads.payload_pipeline._try_once",
            new=AsyncMock(side_effect=[fail, fail, ok]),
        ),
        patch(
            "specs.payloads.payload_pipeline.llm_suggest_payload",
            new=AsyncMock(
                return_value={
                    "ok": True,
                    "request": {"body": {"plan_id": "pro"}, "path_params": {}, "query": {}},
                }
            ),
        ),
        patch("specs.payloads.payload_pipeline._write_working_payload", return_value={
            "payload": {"id": 1},
            "payload_set": {"version": 1, "active": True},
            "overlay_written": True,
        }),
        patch("specs.payloads.payload_pipeline.settings") as settings,
    ):
        settings.default_environment = "dev"
        settings.spt_payload_llm_fallback = True
        out = await ensure_working_payload(
            service="am-subscription",
            environment="dev",
            method="POST",
            path="/subscriptions",
            allow_llm=True,
            max_attempts=3,
            write_back=True,
        )

    assert out["ok"] is True
    assert out["attempts_used"] == 3
    assert out["source"] == "llm-fallback"
    assert len(out["attempts"]) == 3
    assert out["attempts"][0]["ok"] is False
    assert out["attempts"][2]["ok"] is True
    assert out["request"]["body"] == {"plan_id": "pro"}
    assert out["response"]["status_code"] == 200
    assert out["response"]["body"] == {"id": "1"}
    assert out["attempts"][0]["response"]["body"] == {"detail": "bad plan"}


@pytest.mark.asyncio
async def test_ensure_working_prefer_stored_skips_llm_on_pass():
    stored = {
        "method": "GET",
        "path": "/health",
        "api_id": "health",
        "query": {},
        "path_params": {},
    }
    with (
        patch(
            "specs.payloads.payload_pipeline._try_once",
            new=AsyncMock(return_value={"status_code": 200, "body": {"ok": True}}),
        ) as try_mock,
        patch(
            "specs.payloads.payload_pipeline.llm_suggest_payload",
            new=AsyncMock(),
        ) as llm_mock,
        patch("specs.payloads.payload_pipeline._write_working_payload", return_value={
            "payload_set": {"version": 1, "active": True},
            "overlay_written": True,
        }),
        patch("specs.payloads.payload_pipeline.settings") as settings,
    ):
        settings.default_environment = "dev"
        settings.spt_payload_llm_fallback = True
        out = await ensure_working_payload(
            service="am-subscription",
            environment="dev",
            prefer_stored=True,
            initial_request=stored,
            initial_source="set",
            max_attempts=3,
            write_back=True,
        )

    assert out["ok"] is True
    assert out["source"] == "set"
    assert out["attempts_used"] == 1
    try_mock.assert_awaited_once()
    llm_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_all_aggregates_counts():
    apis = {
        "apis": [
            {"id": "a", "method": "GET", "path": "/health"},
            {"id": "b", "method": "POST", "path": "/subscriptions"},
        ]
    }
    with (
        patch("specs.catalog.openapi_sync.sync_openapi_for_service", return_value={"ok": True}),
        patch("specs.payloads.payload_store.ensure_payload_set", return_value={"version": 1, "apis": {}}),
        patch("specs.payloads.payload_store.get_payload_set", return_value={"version": 1, "apis": {}}),
        patch("specs.catalog.catalog_loader.load_service_apis", return_value=apis),
        patch(
            "specs.catalog.catalog_loader.load_openapi_document",
            return_value={"operation_count": 2},
        ),
        patch(
            "specs.payloads.payload_pipeline.ensure_working_payload",
            new=AsyncMock(
                side_effect=[
                    {
                        "ok": True,
                        "source": "schema",
                        "attempts_used": 1,
                        "attempts": [{"n": 1, "ok": True}],
                        "final_status": 200,
                        "payload_set": {"version": 1},
                    },
                    {
                        "ok": False,
                        "source": "llm-fallback",
                        "attempts_used": 3,
                        "attempts": [{"n": 1, "ok": False}, {"n": 2, "ok": False}, {"n": 3, "ok": False}],
                        "final_status": 400,
                        "error": "status=400 body=nope",
                    },
                ]
            ),
        ),
        patch("specs.payloads.payload_pipeline.settings") as settings,
    ):
        settings.default_environment = "dev"
        out = await generate_all_payloads(
            service="am-subscription",
            environment="dev",
            max_attempts=3,
        )

    assert out["total"] == 2
    assert out["passed"] == 1
    assert out["failed"] == 1
    assert out["payload_set_version"] == 1
    assert out["results"][1]["attempts_used"] == 3
