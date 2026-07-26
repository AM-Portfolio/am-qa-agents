from __future__ import annotations

from typing import Any

from specs.load.assets import K6_SCRIPT, PLAYWRIGHT_SCRIPT, read_text, sample_payloads
from specs.security.auth_resolver import sanitize_auth_env
from specs.catalog.catalog_loader import default_target_for_service
from specs.config import settings
from specs.persistence.run_store import save_config
from specs.schemas import TestConfigIn

# Seed template names (generic — not product-specific). Run display names are composed at execute.
DEV_SMOKE = "template-dev-k6"
AGENT_SMOKE = "template-agent-k6"
CI_SMOKE = "template-ci-k6"
UI_SMOKE = "template-dev-playwright"
MIXED_SMOKE = "template-dev-mixed"

# Historical seed names still accepted once, then refreshed under template-* names.
_LEGACY_DEV_NAMES = ("default-smoke", "am-analysis-dev-smoke", "template-dev-k6")
_LEGACY_AGENT_NAMES = ("agent-smoke", "am-analysis-agent-smoke", "template-agent-k6")
_LEGACY_CI_NAMES = ("ci-smoke", "am-analysis-ci-smoke", "template-ci-k6")
_LEGACY_UI_NAMES = ("ui-playwright-smoke", "am-modern-ui-playwright-smoke", "template-dev-playwright")
_LEGACY_MIXED_NAMES = ("mixed-smoke", "am-modern-ui-mixed-smoke", "template-dev-mixed")


def compose_run_display_name(
    *,
    service: str | None,
    environment: str | None,
    test_type: str | None,
    audience: str | None,
) -> str:
    """Human-readable run label: one template covers many services."""
    svc = (service or "service").strip() or "service"
    env = (environment or "dev").strip() or "dev"
    tt = (test_type or "k6").strip() or "k6"
    aud = (audience or "developer").strip() or "developer"
    return f"{svc}-{env}-{tt}-{aud}"


def _default_service() -> str:
    return (settings.default_service or "").strip()


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
    service = _default_service()
    return {
        "name": DEV_SMOKE,
        "description": "Developer smoke — service from registration / request",
        "service": service,
        "environment": settings.default_environment,
        "test_type": "k6",
        "run_profile": "debug",
        "audience": "developer",
        "payload_set_version": None,
        "selected_api_ids": None,
        "target_url": default_target_for_service(service, settings.default_environment) if service else (
            settings.poc_target_url or ""
        ),
        "payloads": _base_payloads(),
        "scripts": {
            "k6": read_text(K6_SCRIPT),
            "playwright": read_text(PLAYWRIGHT_SCRIPT),
        },
    }


def agent_config_dict() -> dict[str, Any]:
    """Agent/automation smoke profile — small deterministic load."""
    service = _default_service()
    payloads = _base_payloads()
    payloads["bench_run"] = {"vus": 1, "iterations": 1}
    return {
        "name": AGENT_SMOKE,
        "description": "Agent smoke — small deterministic run for automation",
        "service": service,
        "environment": settings.default_environment,
        "test_type": "k6",
        "run_profile": "load",
        "audience": "agent",
        "payload_set_version": None,
        "selected_api_ids": None,
        "target_url": default_target_for_service(service, settings.default_environment) if service else (
            settings.poc_target_url or ""
        ),
        "payloads": payloads,
        "scripts": {
            "k6": read_text(K6_SCRIPT),
            "playwright": read_text(PLAYWRIGHT_SCRIPT),
        },
    }


def ci_config_dict() -> dict[str, Any]:
    """CI audience — always 1×1 with traces."""
    c = agent_config_dict()
    c["name"] = CI_SMOKE
    c["description"] = "CI smoke — 1 VU × 1 call with traces"
    c["audience"] = "ci"
    return c


def playwright_ui_config_dict() -> dict[str, Any]:
    """Developer Playwright UI smoke via ui-test-agent."""
    service = _default_service()
    return {
        "name": UI_SMOKE,
        "description": "Playwright UI smoke via ui-test-agent",
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
        "target_url": default_target_for_service(service, settings.default_environment) if service else (
            settings.poc_target_url or ""
        ),
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
    c["name"] = MIXED_SMOKE
    c["description"] = "Mixed smoke — k6 APIs then Playwright UI"
    c["test_type"] = "mixed"
    c["ui_profile"] = settings.ui_test_default_profile
    c["login_mode"] = "demo"
    return c


def _refresh_profile(c: dict[str, Any]) -> dict[str, Any]:
    c = dict(c)
    service = c.get("service") or _default_service()
    env = c.get("environment") or settings.default_environment
    resolved = default_target_for_service(service, env) if service else (settings.poc_target_url or "")
    cur = str(c.get("target_url") or "").rstrip("/")
    if not cur or ".svc.cluster.local" in cur:
        c["target_url"] = resolved
    if c.get("name") == UI_SMOKE:
        c["test_type"] = "playwright"
        c.setdefault("ui_profile", settings.ui_test_default_profile)
    elif c.get("name") == MIXED_SMOKE:
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


def _first_by_names(by_name: dict[str, Any], names: tuple[str, ...]) -> dict[str, Any] | None:
    for n in names:
        if by_name.get(n):
            return by_name[n]
    return None


def ensure_default_config() -> dict[str, Any]:
    """Ensure developer + agent seed profiles exist; return the developer profile."""
    from specs.persistence.run_store import list_configs

    configs = list_configs()
    by_name = {c.get("name"): c for c in configs}

    # Accept legacy seed names once, then refresh under template-* names
    legacy_dev = _first_by_names(by_name, _LEGACY_DEV_NAMES)
    if legacy_dev:
        if legacy_dev.get("name") != DEV_SMOKE:
            legacy_dev = dict(legacy_dev)
            legacy_dev["name"] = DEV_SMOKE
            legacy_dev.pop("id", None)
        developer = _refresh_profile(legacy_dev)
    else:
        developer = save_config(default_config_dict())

    for name, factory, aliases in (
        (AGENT_SMOKE, agent_config_dict, _LEGACY_AGENT_NAMES),
        (CI_SMOKE, ci_config_dict, _LEGACY_CI_NAMES),
        (UI_SMOKE, playwright_ui_config_dict, _LEGACY_UI_NAMES),
        (MIXED_SMOKE, mixed_ui_api_config_dict, _LEGACY_MIXED_NAMES),
    ):
        existing = _first_by_names(by_name, aliases)
        if existing:
            if existing.get("name") != name:
                existing = dict(existing)
                existing["name"] = name
                existing.pop("id", None)
            _refresh_profile(existing)
        else:
            save_config(factory())

    return developer


def config_from_request(body: TestConfigIn | dict[str, Any]) -> dict[str, Any]:
    if isinstance(body, TestConfigIn):
        data = body.model_dump()
    else:
        data = dict(body)
    base = default_config_dict()
    service = data.get("service") or base.get("service") or _default_service()
    environment = data.get("environment") or base.get("environment") or settings.default_environment
    if data.get("target_url"):
        base["target_url"] = data["target_url"]
    elif service:
        base["target_url"] = default_target_for_service(service, environment)
    else:
        base["target_url"] = settings.poc_target_url or ""
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
        "ui_target_url",
        "report_formats",
    ):
        if data.get(key) is not None:
            base[key] = data[key]
    if data.get("payloads"):
        for key, val in data["payloads"].items():
            if val is not None:
                base["payloads"][key] = val
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
