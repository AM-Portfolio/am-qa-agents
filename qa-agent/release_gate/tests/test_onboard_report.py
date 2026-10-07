"""Unit tests for onboard step report helpers + smoke classification."""

from __future__ import annotations

import json
from pathlib import Path

from orchestrator.activities.onboard_report import (
    apis_tools_parity,
    build_report,
    classify_smoke_failure,
    make_step,
    normalize_env,
    path_template_key,
    persist_latest_report,
    load_latest_report,
)


def test_normalize_env_dig_to_dev():
    assert normalize_env("dig") == "dev"
    assert normalize_env("DEV") == "dev"
    assert normalize_env("preprod") == "preprod"


def test_make_step_required_hard_fail():
    step = make_step("openapi_sync", ok=False, status="openapi_unavailable", error="502")
    assert step["required"] is True
    assert step["hard_fail"] is True
    assert step["ok"] is False


def test_make_step_soft_prepare_mcp():
    step = make_step(
        "prepare_mcp",
        ok=True,
        status="warn_mapped_empty",
        hard_fail=False,
    )
    assert step["required"] is False
    assert step["hard_fail"] is False


def test_classify_smoke_auth_hard():
    hard, status, _ = classify_smoke_failure(
        {"ok": False, "status": 401, "error": "JWKS kid mismatch", "body": {}}
    )
    assert hard is True
    assert status == "auth_jwks_mismatch"


def test_classify_smoke_lago_soft():
    hard, status, err = classify_smoke_failure(
        {
            "ok": False,
            "status": 500,
            "error": "LAGO_API_ERROR",
            "body": {"code": "LAGO_API_ERROR", "message": "upstream"},
        }
    )
    assert hard is False
    assert status == "billing_dependency"
    assert "LAGO" in err or "lago" in err.lower()


def test_classify_smoke_not_found_soft():
    hard, status, _ = classify_smoke_failure(
        {"ok": False, "status": 404, "body": {"code": "NOT_FOUND"}}
    )
    assert hard is False
    assert status == "billing_dependency"


def test_path_template_key_and_parity():
    assert path_template_key("get", "/subscriptions/{id}/") == "GET /subscriptions/{}"
    assert path_template_key(
        "GET", "/admin/users/Munish.prime"
    ) == path_template_key("GET", "/admin/users/{user_id}")
    assert path_template_key(
        "GET", "/admin/users/ssd2658"
    ) == path_template_key("GET", "/admin/users/{user_id}")
    apis = [
        {"method": "GET", "path": "/subscriptions/plans"},
        {"method": "POST", "path": "/subscriptions"},
        {"method": "GET", "path": "/admin/users/Munish.prime", "path_template": "/admin/users/{user_id}"},
        {"method": "PATCH", "path": "/admin/users/ssd2658"},
    ]
    tools = [
        {"method": "GET", "path": "/subscriptions/plans"},
        {"method": "POST", "path": "/subscriptions"},
        {"method": "GET", "path": "/admin/users/{user_id}"},
        {"method": "PATCH", "path": "/admin/users/{user_id}"},
    ]
    p = apis_tools_parity(apis, tools)
    assert p["ok"] is True
    assert p["api_count"] == 4

    tools_missing = [{"method": "GET", "path": "/subscriptions/plans"}]
    p2 = apis_tools_parity(apis[:2], tools_missing)
    assert p2["ok"] is False
    assert any("POST" in m for m in p2["missing_tools"])


def test_build_report_fail_fast_and_persist(tmp_path: Path):
    steps = [
        make_step("analyze", ok=True, status="ok"),
        make_step(
            "openapi_sync",
            ok=False,
            status="openapi_unavailable",
            error="502",
            evidence={"http_status": 502},
        ),
    ]
    report = build_report(
        service="am-subscription",
        environment="dig",
        workflow_id="wf-1",
        steps=steps,
        api_count=0,
    )
    assert report["ok"] is False
    assert report["failed_step"] == "openapi_sync"
    assert report["environment"] == "dev"

    path = persist_latest_report(str(tmp_path), "am-subscription", "dig", report)
    assert Path(path).is_file()
    loaded = load_latest_report(str(tmp_path), "am-subscription", "dev")
    assert loaded is not None
    assert loaded["workflow_id"] == "wf-1"
    assert json.loads(Path(path).read_text(encoding="utf-8"))["failed_step"] == "openapi_sync"


def test_build_report_soft_lago_still_ok():
    steps = [
        make_step("analyze", ok=True, status="ok"),
        make_step(
            "tools_smoke",
            ok=True,
            status="billing_dependency",
            error="LAGO_API_ERROR",
            hard_fail=False,
        ),
    ]
    report = build_report(
        service="am-subscription",
        environment="dev",
        workflow_id="wf-2",
        steps=steps,
        warnings=["tools_smoke:billing_dependency"],
    )
    assert report["ok"] is True
    assert report["failed_step"] is None
    assert any("billing" in w for w in report["warnings"])
