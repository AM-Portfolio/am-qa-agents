"""Derive product HTTPS and infra URLs from APP_ENV / DEFAULT_ENVIRONMENT.

Product surfaces (SPA, analysis, identity, ui-test ingress) use public domains.
Infra (MCP gateway, etc.) stays on cluster DNS.
"""
from __future__ import annotations

from typing import Literal

ProductSurface = Literal["modern_ui", "analysis", "identity", "ui_test", "spt"]

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

_PRODUCT_PATH: dict[ProductSurface, str] = {
    "modern_ui": "",
    "analysis": "/analysis",
    "identity": "/identity",
    "ui_test": "/ui-test",
    "spt": "/spt-poc",
}


def normalize_env(raw: str | None) -> str | None:
    """Map APP_ENV / DEFAULT_ENVIRONMENT to canonical key, or None if local/unknown."""
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


def product_url(env: str, surface: ProductSurface) -> str:
    host = public_host(env).rstrip("/")
    path = _PRODUCT_PATH[surface]
    return f"{host}{path}" if path else host


def apps_namespace(env: str) -> str:
    key = normalize_env(env) or "dev"
    return _APPS_NS[key]


def infra_mcp_gateway(env: str) -> str:
    """LLM / agent gateway (not finance tools)."""
    ns = apps_namespace(env)
    return f"http://am-mcp-gateway.{ns}.svc.cluster.local:8120"


def infra_mcp_server(env: str) -> str:
    """am-mcp-server ClusterIP base (SSE at /sse, message at /message — no /mcp prefix)."""
    ns = apps_namespace(env)
    return f"http://am-mcp-server.{ns}.svc.cluster.local:8080"


def public_mcp_server(env: str) -> str:
    """Public ingress base with /mcp prefix (Traefik strip → pod /sse). Prefer for local laptop."""
    return f"{public_host(env).rstrip('/')}/mcp"


def is_cluster_dns(url: str | None) -> bool:
    return bool(url) and ".svc.cluster.local" in url


def needs_product_fill(url: str | None) -> bool:
    """True when unset or still pointing at in-cluster DNS."""
    if url is None:
        return True
    cur = url.strip()
    return not cur or is_cluster_dns(cur)
