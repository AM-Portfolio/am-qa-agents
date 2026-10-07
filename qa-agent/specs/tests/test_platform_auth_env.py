"""MCP/OpenAPI platform auth must follow Specs environment, not SPT_IDENTITY_URL pin."""

from specs.catalog.catalog_loader import _identity_url_for_platform_auth


def test_platform_auth_identity_follows_env():
    assert _identity_url_for_platform_auth("dev") == "https://am-dev.asrax.in/identity"
    assert _identity_url_for_platform_auth("dig") == "https://am-dev.asrax.in/identity"
    assert _identity_url_for_platform_auth("prod") == "https://am.asrax.in/identity"
