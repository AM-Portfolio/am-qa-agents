"""GrowthBook feature-flag helpers for QA API flows."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Throwaway register → full auth/user/subscription API pack → cleanup.
QA_AUTH_EPHEMERAL_USER_FLOWS = "qa-auth-ephemeral-user-flows"


def _env_truthy(name: str) -> bool | None:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return None
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return None


def default_ephemeral_user_enabled(environment: str) -> bool:
    """Defaults when GrowthBook is unavailable or the flag is unset.

    preprod/dev: on. prod: on for now (turn off later via GrowthBook).
    """
    _ = (environment or "prod").lower()
    return True


def _extract_bool(feature: Any) -> bool | None:
    if isinstance(feature, bool):
        return feature
    if not isinstance(feature, dict):
        return None
    for key in ("defaultValue", "defaultValueBoolean", "value", "on"):
        if key in feature and isinstance(feature[key], bool):
            return feature[key]
    # GrowthBook REST feature: environments.<env>.enabled / defaultValue
    envs = feature.get("environments")
    if isinstance(envs, dict):
        for env_body in envs.values():
            if not isinstance(env_body, dict):
                continue
            if isinstance(env_body.get("enabled"), bool) and not env_body.get("enabled"):
                return False
            dv = env_body.get("defaultValue")
            if isinstance(dv, bool):
                return dv
            if isinstance(dv, str) and dv.lower() in {"true", "false"}:
                return dv.lower() == "true"
    return None


def _lookup_flag(flags: Any, key: str) -> bool | None:
    if not isinstance(flags, dict):
        return None
    # Client SDK shape: {features: {key: {...}}}
    features = flags.get("features") if "features" in flags else flags
    if isinstance(features, dict) and key in features:
        return _extract_bool(features[key])
    # Admin list: {features: [{id, ...}]}
    rows = flags.get("features") if isinstance(flags.get("features"), list) else None
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            fid = str(row.get("id") or row.get("key") or "")
            if fid == key:
                return _extract_bool(row)
    # Nested under data
    data = flags.get("data")
    if isinstance(data, dict):
        return _lookup_flag(data, key)
    return None


def fetch_growthbook_features() -> dict[str, Any]:
    """Best-effort GrowthBook snapshot (client SDK or admin API)."""
    if os.getenv("QA_AGENT_SKIP_GROWTHBOOK", "").lower() in {"1", "true", "yes"}:
        return {"skipped": True, "reason": "QA_AGENT_SKIP_GROWTHBOOK", "flags": {}}

    host = (
        os.getenv("GROWTHBOOK_API_HOST")
        or os.getenv("GROWTHBOOK_URL")
        or os.getenv("GB_API_URL")
        or os.getenv("GB_APP_ORIGIN")
        or ""
    ).rstrip("/")
    client_key = (
        os.getenv("GROWTHBOOK_CLIENT_KEY")
        or os.getenv("GROWTHBOOK_SDK_KEY")
        or os.getenv("GB_CLIENT_KEY")
        or ""
    ).strip()
    api_key = (
        os.getenv("GROWTHBOOK_API_KEY") or os.getenv("GB_API_KEY") or ""
    ).strip()

    if not host:
        return {"skipped": True, "reason": "missing_growthbook_host", "flags": {}}

    try:
        with httpx.Client(timeout=12.0) as client:
            if client_key:
                url = f"{host}/api/features/{client_key}"
                resp = client.get(url)
                if resp.status_code < 400:
                    data = resp.json()
                    return {
                        "ok": True,
                        "source": "client_sdk",
                        "flags": data if isinstance(data, dict) else {"raw": data},
                    }
            if api_key:
                url = f"{host}/api/v1/features"
                resp = client.get(url, headers={"Authorization": f"Bearer {api_key}"})
                if resp.status_code < 400:
                    data = resp.json()
                    return {
                        "ok": True,
                        "source": "admin_api",
                        "flags": data if isinstance(data, dict) else {"raw": data},
                    }
                return {
                    "ok": False,
                    "source": "admin_api",
                    "http_status": resp.status_code,
                    "flags": {},
                }
    except httpx.HTTPError as exc:
        logger.warning("GrowthBook fetch failed: %s", exc)
        return {"ok": False, "error": str(exc), "flags": {}}

    return {"skipped": True, "reason": "missing_growthbook_keys", "flags": {}}


def resolve_feature_flag(
    key: str,
    *,
    environment: str = "prod",
    default: bool | None = None,
) -> dict[str, Any]:
    """Resolve a boolean feature flag with env override → GrowthBook → default."""
    slug = key.upper().replace("-", "_")
    overrides = [f"QA_FLAG_{slug}", slug]
    if key == QA_AUTH_EPHEMERAL_USER_FLOWS:
        overrides = ["FLOW_EPHEMERAL_USER", "QA_AUTH_EPHEMERAL_USER_FLOWS", *overrides]
    for name in overrides:
        forced = _env_truthy(name)
        if forced is not None:
            return {
                "key": key,
                "enabled": forced,
                "source": f"env:{name}",
                "environment": environment,
            }

    snap = fetch_growthbook_features()
    looked = _lookup_flag(snap.get("flags") or {}, key)
    if looked is not None:
        return {
            "key": key,
            "enabled": looked,
            "source": f"growthbook:{snap.get('source') or 'unknown'}",
            "environment": environment,
            "snapshot": {"ok": snap.get("ok"), "skipped": snap.get("skipped")},
        }

    enabled = (
        default
        if default is not None
        else default_ephemeral_user_enabled(environment)
    )
    return {
        "key": key,
        "enabled": enabled,
        "source": "default",
        "environment": environment,
        "snapshot": {
            "ok": snap.get("ok"),
            "skipped": snap.get("skipped"),
            "reason": snap.get("reason") or snap.get("error"),
        },
    }


def ephemeral_user_flows_enabled(environment: str = "prod") -> dict[str, Any]:
    return resolve_feature_flag(
        QA_AUTH_EPHEMERAL_USER_FLOWS,
        environment=environment,
        default=default_ephemeral_user_enabled(environment),
    )
