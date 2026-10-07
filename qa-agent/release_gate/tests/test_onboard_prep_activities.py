"""Activity-level tests for onboard prep (mocked domain calls)."""

from __future__ import annotations

import pytest

from orchestrator.activities import onboard_prep as prep


@pytest.mark.asyncio
async def test_openapi_sync_unavailable(monkeypatch):
    def _boom(*_a, **_k):
        return {"ok": False, "error": "openapi_unavailable", "openapi_url": "http://x/openapi.json"}

    monkeypatch.setattr(
        "specs.catalog.openapi_sync.sync_openapi_for_service",
        _boom,
        raising=False,
    )
    # Patch where activity imports from
    import specs.catalog.openapi_sync as sync_mod

    monkeypatch.setattr(sync_mod, "sync_openapi_for_service", _boom)

    step = await prep.activity_onboard_openapi_sync(
        {"service": "am-subscription", "environment": "dev"}
    )
    assert step["ok"] is False
    assert step["status"] == "openapi_unavailable"
    assert step["hard_fail"] is True


@pytest.mark.asyncio
async def test_apis_health_fallback(monkeypatch):
    import specs.catalog.catalog_loader as cl

    monkeypatch.setattr(
        cl,
        "load_service_apis",
        lambda *_a, **_k: {
            "source": "health-fallback",
            "apis": [{"id": "actuator.health", "method": "GET", "path": "/actuator/health"}],
        },
    )
    step = await prep.activity_onboard_apis(
        {"service": "am-subscription", "environment": "dev"}
    )
    assert step["ok"] is False
    assert step["status"] == "apis_health_fallback"


@pytest.mark.asyncio
async def test_tools_smoke_lago_soft(monkeypatch):
    import specs.openapi_tools.registry as reg

    monkeypatch.setattr(
        reg,
        "list_tools",
        lambda **_k: {
            "tools": [
                {"name": "svc_health", "method": "GET", "path": "/health"},
                {"name": "svc_me", "method": "GET", "path": "/subscriptions/me"},
            ]
        },
    )

    def _call(name, *_a, **_k):
        if "health" in name:
            return {"ok": True, "status": 200, "body": {"status": "UP"}}
        return {
            "ok": False,
            "status": 500,
            "error": "LAGO_API_ERROR",
            "body": {"code": "LAGO_API_ERROR"},
        }

    monkeypatch.setattr(reg, "call_tool", _call)

    step = await prep.activity_onboard_tools_smoke(
        {"service": "am-subscription", "environment": "dev"}
    )
    assert step["hard_fail"] is False
    assert step["ok"] is True
    assert step["status"] == "billing_dependency"


@pytest.mark.asyncio
async def test_tools_smoke_auth_hard(monkeypatch):
    import specs.openapi_tools.registry as reg

    monkeypatch.setattr(
        reg,
        "list_tools",
        lambda **_k: {
            "tools": [
                {"name": "svc_health", "method": "GET", "path": "/health"},
            ]
        },
    )
    monkeypatch.setattr(
        reg,
        "call_tool",
        lambda *_a, **_k: {
            "ok": False,
            "status": 401,
            "error": "JWT signing key / JWKS kid mismatch",
            "body": {},
        },
    )

    step = await prep.activity_onboard_tools_smoke(
        {"service": "am-subscription", "environment": "dev"}
    )
    assert step["hard_fail"] is True
    assert step["ok"] is False
    assert step["status"] == "auth_jwks_mismatch"


@pytest.mark.asyncio
async def test_inline_fail_fast_after_openapi(monkeypatch):
    from orchestrator import temporal_api as tapi

    async def _analyze(args):
        return {
            "step": "analyze",
            "ok": True,
            "status": "ok",
            "required": True,
            "hard_fail": False,
            "evidence": {"target_url": "http://svc"},
            "error": None,
            "duration_ms": 1,
        }

    async def _openapi(args):
        return {
            "step": "openapi_sync",
            "ok": False,
            "status": "openapi_unavailable",
            "required": True,
            "hard_fail": True,
            "evidence": {},
            "error": "502",
            "duration_ms": 1,
        }

    async def _persist(args):
        return {"ok": True}

    monkeypatch.setattr(prep, "activity_onboard_analyze", _analyze)
    monkeypatch.setattr(prep, "activity_onboard_openapi_sync", _openapi)
    monkeypatch.setattr(prep, "activity_onboard_persist_report", _persist)

    # Inline imports activities from module — patch temporal_api's imports path
    monkeypatch.setattr(
        "orchestrator.activities.onboard_prep.activity_onboard_analyze",
        _analyze,
    )
    monkeypatch.setattr(
        "orchestrator.activities.onboard_prep.activity_onboard_openapi_sync",
        _openapi,
    )
    monkeypatch.setattr(
        "orchestrator.activities.onboard_prep.activity_onboard_persist_report",
        _persist,
    )

    report = await tapi.run_service_onboard_prep_inline(
        {"service": "am-subscription", "environment": "dev"}
    )
    assert report["ok"] is False
    assert report["failed_step"] == "openapi_sync"
    assert [s["step"] for s in report["steps"]] == ["analyze", "openapi_sync"]
