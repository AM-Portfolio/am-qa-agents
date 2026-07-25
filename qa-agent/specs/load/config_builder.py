from __future__ import annotations

from typing import Any

from spt.assets import K6_SCRIPT, PLAYWRIGHT_SCRIPT, read_text, sample_payloads
from spt.auth_resolver import sanitize_auth_env
from spt.catalog_loader import default_target_for_service
from spt.config import settings
from spt.run_store import save_config
from spt.schemas import TestConfigIn


def _base_payloads() -> dict[str, Any]:
    payloads = sample_payloads()
    return {
        **payloads,
        "bench_run": {"vus": 1, "duration": "1s", "iterations": 1},
        "auth_env": {
            "username": settings.spt_auth_username,
        },
    }


def default_config_dict() -> dict[str, Any]:
    """Developer-facing smoke profile (portal default)."""
    service = "am-analysis"
    return {
        "name": "am-analysis-dev-smoke",
        "description": "Developer smoke — am-analysis dashboard APIs",
        "service": service,
        "environment": settings.default_environment,
        "test_type": "k6",
        "run_profile": "debug",
        "audience": "developer",
        "payload_set_version": None,
        "selected_api_ids": None,
        "target_url": default_target_for_service(service, settings.default_environment),
        "payloads": _base_payloads(),
        "scripts": {
            "k6": read_text(K6_SCRIPT),
            "playwright": read_text(PLAYWRIGHT_SCRIPT),
        },
    }


def agent_config_dict() -> dict[str, Any]:
    """Agent/automation smoke profile — small deterministic load."""
    service = "am-analysis"
    payloads = _base_payloads()
    payloads["bench_run"] = {"vus": 1, "iterations": 1}
    return {
        "name": "am-analysis-agent-smoke",
        "description": "Agent smoke — small deterministic run for automation",
        "service": service,
        "environment": settings.default_environment,
        "test_type": "k6",
        "run_profile": "load",
        "audience": "agent",
        "payload_set_version": None,
        "selected_api_ids": None,
        "target_url": default_target_for_service(service, settings.default_environment),
        "payloads": payloads,
        "scripts": {
            "k6": read_text(K6_SCRIPT),
            "playwright": read_text(PLAYWRIGHT_SCRIPT),
        },
    }


def ci_config_dict() -> dict[str, Any]:
    """CI audience — always 1×1 with traces."""
    c = agent_config_dict()
    c["name"] = "am-analysis-ci-smoke"
    c["description"] = "CI smoke — 1 VU × 1 call with traces"
    c["audience"] = "ci"
    return c


def playwright_ui_config_dict() -> dict[str, Any]:
    """Developer Playwright UI smoke via ui-test-agent."""
    service = "am-modern-ui"
    return {
        "name": "am-modern-ui-playwright-smoke",
        "description": "Playwright UI smoke — am-modern-ui via ui-test-agent",
        "service": service,
        "environment": settings.default_environment,
        "test_type": "playwright",
        "run_profile": "load",
        "audience": "developer",
        "payload_set_version": None,
        "selected_api_ids": None,
        "ui_profile": settings.ui_test_default_profile,
        "ui_suite": None,
        "login_mode": "demo",
        "target_url": default_target_for_service(service, settings.default_environment),
        "payloads": {
            "bench_run": {},
            "playwright_import": sample_payloads().get("playwright_import") or {},
            "auth_env": {"username": settings.spt_auth_username},
        },
        "scripts": {
            "playwright": read_text(PLAYWRIGHT_SCRIPT),
        },
    }


def mixed_ui_api_config_dict() -> dict[str, Any]:
    """Mixed k6 + Playwright profile (API and UI both enabled)."""
    c = default_config_dict()
    c["name"] = "am-modern-ui-mixed-smoke"
    c["description"] = "Mixed smoke — k6 APIs then Playwright UI"
    c["service"] = "am-modern-ui"
    c["test_type"] = "mixed"
    c["ui_profile"] = settings.ui_test_default_profile
    c["login_mode"] = "demo"
    c["target_url"] = default_target_for_service(
        "am-modern-ui", settings.default_environment
    )
    return c


def _refresh_profile(c: dict[str, Any]) -> dict[str, Any]:
    c = dict(c)
    service = c.get("service") or "am-analysis"
    env = c.get("environment") or settings.default_environment
    resolved = default_target_for_service(service, env)
    cur = str(c.get("target_url") or "").rstrip("/")
    # Fix common mis-wire: modern-ui profiles that inherited /analysis from POC default
    if service == "am-modern-ui" and (not cur or cur.endswith("/analysis") or ".svc.cluster.local" in cur):
        c["target_url"] = resolved
    elif not cur or ".svc.cluster.local" in cur:
        c["target_url"] = resolved
    # Ensure UI / mixed seeds keep an explicit test_type
    if c.get("name") == "am-modern-ui-playwright-smoke":
        c["test_type"] = "playwright"
        c.setdefault("ui_profile", settings.ui_test_default_profile)
    elif c.get("name") == "am-modern-ui-mixed-smoke":
        c["test_type"] = "mixed"
        c.setdefault("ui_profile", settings.ui_test_default_profile)
    payloads = dict(c.get("payloads") or {})
    auth = dict(payloads.get("auth_env") or {})
    auth.setdefault("username", settings.spt_auth_username)
    payloads["auth_env"] = auth
    c["payloads"] = payloads
    if not c.get("audience"):
        name = c.get("name") or ""
        if "agent" in name:
            c["audience"] = "agent"
        elif "ci" in name:
            c["audience"] = "ci"
        else:
            c["audience"] = "developer"
    return save_config(c)


def ensure_default_config() -> dict[str, Any]:
    """Ensure developer + agent seed profiles exist; return the developer profile."""
    from spt.run_store import list_configs

    configs = list_configs()
    by_name = {c.get("name"): c for c in configs}

    developer = by_name.get("am-analysis-dev-smoke") or by_name.get("default-smoke")
    if developer:
        developer = _refresh_profile(developer)
    else:
        developer = save_config(default_config_dict())

    agent = by_name.get("am-analysis-agent-smoke")
    if agent:
        _refresh_profile(agent)
    else:
        save_config(agent_config_dict())

    ci = by_name.get("am-analysis-ci-smoke")
    if ci:
        _refresh_profile(ci)
    else:
        save_config(ci_config_dict())

    ui = by_name.get("am-modern-ui-playwright-smoke")
    if ui:
        _refresh_profile(ui)
    else:
        save_config(playwright_ui_config_dict())

    mixed = by_name.get("am-modern-ui-mixed-smoke")
    if mixed:
        _refresh_profile(mixed)
    else:
        save_config(mixed_ui_api_config_dict())

    return developer


def config_from_request(body: TestConfigIn | dict[str, Any]) -> dict[str, Any]:
    if isinstance(body, TestConfigIn):
        data = body.model_dump()
    else:
        data = dict(body)
    base = default_config_dict()
    service = data.get("service") or base.get("service") or "am-analysis"
    environment = data.get("environment") or base.get("environment") or settings.default_environment
    if data.get("target_url"):
        base["target_url"] = data["target_url"]
    else:
        base["target_url"] = default_target_for_service(service, environment)
    if data.get("name"):
        base["name"] = data["name"]
    for key in (
        "description",
        "service",
        "environment",
        "test_type",
        "run_profile",
        "openapi_version",
        "audience",
        "payload_set_version",
        "selected_api_ids",
        "ui_profile",
        "ui_suite",
        "ui_profiles",
        "login_mode",
        "baseline_mode",
        "design_review_enabled",
        "report_formats",
    ):
        if data.get(key) is not None:
            base[key] = data[key]
    if data.get("payloads"):
        for key, val in data["payloads"].items():
            if val is not None:
                base["payloads"][key] = val
        # Keep top-level payload_set_version in sync with payloads when set
        psv = data["payloads"].get("payload_set_version")
        if psv is not None:
            base["payload_set_version"] = psv
    if data.get("scripts"):
        base["scripts"].update(data["scripts"])
    return base


def snapshot_for_run(config: dict[str, Any]) -> dict[str, Any]:
    payloads = dict(config.get("payloads") or {})
    auth = sanitize_auth_env(payloads.get("auth_env"))
    if auth:
        payloads["auth_env"] = auth
    else:
        payloads.pop("auth_env", None)
    # Never persist secrets or generated k6 scripts in run history
    payloads.pop("k6_import", None)
    scripts = dict(config.get("scripts") or {})
    scripts.pop("k6", None)
    return {
        "config_id": config.get("id"),
        "config_name": config.get("name", "unnamed"),
        "service": config.get("service"),
        "environment": config.get("environment"),
        "test_type": config.get("test_type"),
        "run_profile": config.get("run_profile"),
        "audience": config.get("audience"),
        "payload_set_version": config.get("payload_set_version"),
        "target_url": config.get("target_url"),
        "payloads": payloads,
        "scripts": scripts,
    }
