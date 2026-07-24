"""Derive product HTTPS and infra URLs from APP_ENV.

Product surfaces (SPA) use public domains. Infra (MCP gateway, Qdrant) stays on cluster DNS.
"""
from __future__ import annotations

_PUBLIC_HOST: dict[str, str] = {
    "dev": "https://am-dev.asrax.in",
    "preprod": "https://am.asrax.in",
    "prod": "https://am.asrax.in",
    "production": "https://am.asrax.in",
}

_APPS_NS: dict[str, str] = {
    "dev": "am-apps-dev",
    "preprod": "am-apps-preprod",
    "prod": "am-apps-prod",
    "production": "am-apps-prod",
}


def normalize_env(raw: str | None) -> str | None:
    if not raw:
        return None
    key = raw.strip().lower()
    if key in ("development", "local", "test"):
        return None
    if key in _PUBLIC_HOST:
        return "prod" if key == "production" else key
    return None


def public_host(env: str) -> str:
    key = normalize_env(env) or "dev"
    return _PUBLIC_HOST[key]


def modern_ui_url(env: str) -> str:
    return public_host(env).rstrip("/")


def apps_namespace(env: str) -> str:
    key = normalize_env(env) or "dev"
    return _APPS_NS[key]


def infra_mcp_gateway(env: str) -> str:
    ns = apps_namespace(env)
    return f"http://am-mcp-gateway.{ns}.svc.cluster.local:8120"


def infra_qdrant_host(env: str) -> str:
    # Shared AI namespace across envs today
    return "qdrant.am-ai.svc.cluster.local"


def is_cluster_dns(url: str | None) -> bool:
    return bool(url) and ".svc.cluster.local" in url


def is_local_url(url: str | None) -> bool:
    if not url:
        return True
    u = url.strip().lower()
    return u.startswith("http://localhost") or u.startswith("http://127.0.0.1")
