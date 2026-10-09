"""Flow runner pairs identity + subscription hosts; health falls back on 404."""
from __future__ import annotations

from specs.flows import runner


def test_request_envelope_redacts_password_and_bearer():
    env = runner._request_envelope(
        method="post",
        url="https://am.asrax.in/identity/auth/login",
        path="/auth/login",
        headers={
            "Accept": "application/json",
            "Authorization": "Bearer super-secret-token",
        },
        body={"username": "u@example.com", "password": "hunter2"},
    )
    assert env["method"] == "POST"
    assert env["url"] == "https://am.asrax.in/identity/auth/login"
    assert env["path"] == "/auth/login"
    assert env["headers"]["Authorization"] == "Bearer <redacted>"
    assert env["headers"]["Accept"] == "application/json"
    assert env["body"]["username"] == "u@example.com"
    assert env["body"]["password"] == "<redacted>"


def test_creds_for_run_pairs_prod_hosts(monkeypatch):
    monkeypatch.setattr(
        runner,
        "resolve_credential",
        lambda _cid: {
            "username": "u@example.com",
            "password": "secret",
            "env": "dev",
            "base_url": "https://am-dev.asrax.in/identity",
        },
    )
    user, password, identity, gateway, eff = runner._creds_for_run(
        credential_id="spt-login-dev", env="prod"
    )
    assert user == "u@example.com"
    assert password == "secret"
    assert eff == "prod"
    assert identity == "https://am.asrax.in/identity"
    assert gateway == "https://am.asrax.in"


def test_service_base_url_uses_catalog_for_market(monkeypatch):
    monkeypatch.setattr(
        "specs.catalog.catalog_loader.default_target_for_service",
        lambda service, environment: {
            ("am-market-data", "dev"): "https://am-dev.asrax.in/market",
            ("am-market-data", "prod"): "https://am.asrax.in/market",
        }.get((service, environment), ""),
    )
    dig = runner._service_base_url(
        "am-market-data",
        env="dev",
        identity_base="https://am-dev.asrax.in/identity",
        gateway_host="https://am-dev.asrax.in",
    )
    assert dig == "https://am-dev.asrax.in/market"
    # identity services stay on identity surface
    assert (
        runner._service_base_url(
            "am-identity",
            env="dev",
            identity_base="https://am-dev.asrax.in/identity",
            gateway_host="https://am-dev.asrax.in",
        )
        == "https://am-dev.asrax.in/identity"
    )


def test_subscription_health_falls_back_to_plans(monkeypatch):
    class _Resp:
        def __init__(self, status: int, body: dict):
            self.status_code = status
            self._body = body
            self.text = str(body)

        @property
        def is_success(self) -> bool:
            return 200 <= self.status_code < 300

        def json(self):
            return self._body

    calls: list[str] = []

    class _Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def request(self, method, url, headers=None):
            calls.append(url)
            if url.endswith("/subscriptions/health"):
                return _Resp(404, {"detail": "Not Found"})
            return _Resp(200, {"data": [{"code": "am_free"}]})

    monkeypatch.setattr(runner.httpx if hasattr(runner, "httpx") else __import__("httpx"), "Client", _Client)
    # Patch where used: inside function imports httpx — patch httpx.Client globally
    import httpx

    monkeypatch.setattr(httpx, "Client", _Client)

    out = runner._subscription_request(
        host="https://am.asrax.in",
        step_id="sub_health",
        label="sub_health",
        path_hint="/health",
        method="get",
        headers={"Accept": "application/json"},
    )
    assert out["ok"] is True
    assert out["status"] == 200
    assert out["url"].endswith("/subscriptions/plans")
    assert calls[0].endswith("/subscriptions/health")
    assert calls[1].endswith("/subscriptions/plans")
