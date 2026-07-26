"""Derive product HTTPS and infra URLs from APP_ENV / DEFAULT_ENVIRONMENT.

Shared by SPT and UI evidence (single copy).
"""
from __future__ import annotations

import os
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
    "spt": "/qa",
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


def modern_ui_url(env: str) -> str:
    return product_url(env, "modern_ui")


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


def needs_product_fill(url: str | None) -> bool:
    """True when unset or still pointing at in-cluster DNS."""
    if url is None:
        return True
    cur = url.strip()
    return not cur or is_cluster_dns(cur)


def loopback_ui_test_url(port: int | None = None) -> str:
    """In-pod / local colocated UI evidence (one container)."""
    p = port or int(os.getenv("APP_PORT") or os.getenv("QA_AGENT_PORT") or "8150")
    return f"http://127.0.0.1:{p}"
