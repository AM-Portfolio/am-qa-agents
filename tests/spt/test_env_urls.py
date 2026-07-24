"""Tests for APP_ENV → public / infra URL resolver."""
from __future__ import annotations

from spt import env_urls


def test_public_hosts():
    assert env_urls.public_host("dev") == "https://am-dev.asrax.in"
    assert env_urls.public_host("preprod") == "https://am.asrax.in"
    assert env_urls.public_host("prod") == "https://am.asrax.in"
    assert env_urls.public_host("production") == "https://am.asrax.in"


def test_product_urls():
    assert env_urls.product_url("dev", "analysis") == "https://am-dev.asrax.in/analysis"
    assert env_urls.product_url("dev", "identity") == "https://am-dev.asrax.in/identity"
    assert env_urls.product_url("dev", "ui_test") == "https://am-dev.asrax.in/ui-test"
    assert env_urls.product_url("dev", "modern_ui") == "https://am-dev.asrax.in"
    assert env_urls.product_url("preprod", "ui_test") == "https://am.asrax.in/ui-test"


def test_normalize_env():
    assert env_urls.normalize_env("dev") == "dev"
    assert env_urls.normalize_env("production") == "prod"
    assert env_urls.normalize_env("development") is None
    assert env_urls.normalize_env("local") is None


def test_infra_mcp_gateway():
    assert (
        env_urls.infra_mcp_gateway("dev")
        == "http://am-mcp-gateway.am-apps-dev.svc.cluster.local:8120"
    )
    assert (
        env_urls.infra_mcp_gateway("preprod")
        == "http://am-mcp-gateway.am-apps-preprod.svc.cluster.local:8120"
    )


def test_infra_mcp_server():
    assert (
        env_urls.infra_mcp_server("dev")
        == "http://am-mcp-server.am-apps-dev.svc.cluster.local:8080"
    )
    assert env_urls.public_mcp_server("dev") == "https://am-dev.asrax.in/mcp"
    assert env_urls.public_mcp_server("preprod") == "https://am.asrax.in/mcp"


def test_needs_product_fill():
    assert env_urls.needs_product_fill("")
    assert env_urls.needs_product_fill(None)
    assert env_urls.needs_product_fill(
        "http://am-ui-test-agent.am-apps-dev.svc.cluster.local:8130"
    )
    assert not env_urls.needs_product_fill("https://am-dev.asrax.in/ui-test")
