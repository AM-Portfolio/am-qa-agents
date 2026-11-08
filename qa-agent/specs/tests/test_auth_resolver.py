"""Per-run identity URL must follow config.environment, not APP_ENV / SPT_IDENTITY_URL."""
from __future__ import annotations

import asyncio

import pytest

from specs.security.auth_resolver import ensure_auth_env, resolve_identity_url


def test_resolve_identity_prefers_explicit_auth():
    url = resolve_identity_url(
        {"environment": "dev"},
        {"identity_url": "https://custom.example/identity"},
    )
    assert url == "https://custom.example/identity"


def test_resolve_identity_follows_run_env_not_global_pin():
    # dig/dev runs must not inherit SPT_IDENTITY_URL=prod from laptop .env
    assert resolve_identity_url({"environment": "dev"}, {}) == (
        "https://am-dev.asrax.in/identity"
    )
    assert resolve_identity_url({"environment": "dig"}, {}) == (
        "https://am-dev.asrax.in/identity"
    )
    assert resolve_identity_url({"environment": "prod"}, {}) == (
        "https://am.asrax.in/identity"
    )


@pytest.mark.asyncio
async def test_ensure_auth_ignores_orphan_payload_username(monkeypatch):
    """Username-only auth_env must not override SPT_AUTH_USERNAME + password."""
    monkeypatch.setenv("SPT_AUTH_USERNAME", "munish.prime@gmail.com")
    monkeypatch.setenv("SPT_AUTH_PASSWORD", "secret-pass")
    monkeypatch.setattr(
        "specs.security.auth_resolver.settings.spt_auth_username",
        "ssd2658@gmail.com",
    )
    monkeypatch.setattr(
        "specs.security.auth_resolver.settings.spt_auth_password",
        None,
    )

    called: dict[str, str] = {}

    async def _fake_login(identity_url: str, username: str, password: str, **_kw):
        called["url"] = identity_url
        called["user"] = username
        called["pass"] = password
        return {"access_token": "hdr.eyJzdWIiOiJ1MSJ9.sig"}

    monkeypatch.setattr(
        "specs.security.auth_resolver.login_identity",
        _fake_login,
    )

    cfg = {
        "environment": "dev",
        "payloads": {"auth_env": {"username": "ssd2658@gmail.com"}},
    }
    out = await ensure_auth_env(cfg)
    assert called["user"] == "munish.prime@gmail.com"
    assert called["pass"] == "secret-pass"
    assert called["url"] == "https://am-dev.asrax.in/identity"
    assert out["payloads"]["auth_env"]["username"] == "munish.prime@gmail.com"
