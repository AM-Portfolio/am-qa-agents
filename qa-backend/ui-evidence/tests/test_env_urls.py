"""Tests for APP_ENV → public / infra URL resolver."""
from __future__ import annotations

from app import env_urls


def test_public_hosts():
    assert env_urls.public_host("dev") == "https://am-dev.asrax.in"
    assert env_urls.public_host("preprod") == "https://am.asrax.in"
    assert env_urls.public_host("production") == "https://am.asrax.in"


def test_modern_ui_url():
    assert env_urls.modern_ui_url("dev") == "https://am-dev.asrax.in"
    assert env_urls.modern_ui_url("preprod") == "https://am.asrax.in"


def test_normalize_env():
    assert env_urls.normalize_env("dev") == "dev"
    assert env_urls.normalize_env("production") == "prod"
    assert env_urls.normalize_env("development") is None


def test_infra():
    assert (
        env_urls.infra_mcp_gateway("dev")
        == "http://am-mcp-gateway.am-apps-dev.svc.cluster.local:8120"
    )
    assert env_urls.infra_qdrant_host("dev") == "qdrant.am-ai.svc.cluster.local"
