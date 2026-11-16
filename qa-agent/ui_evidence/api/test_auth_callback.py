from urllib.parse import parse_qs

import pytest

from ui_evidence.api import auth_callback


def test_code_exchange_uses_public_pkce_client(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"access_token":"test-token"}'

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(auth_callback.urllib.request, "urlopen", fake_urlopen)

    result = auth_callback._exchange_code_with_keycloak(
        "auth-code", "https://am-dev.asrax.in/qa/ui/callback", "v" * 43
    )

    form = parse_qs(captured["request"].data.decode())
    assert result["access_token"] == "test-token"
    assert form["client_id"] == [auth_callback.settings.KEYCLOAK_QA_CLIENT_ID]
    assert form["code"] == ["auth-code"]
    assert form["redirect_uri"] == ["https://am-dev.asrax.in/qa/ui/callback"]
    assert form["code_verifier"] == ["v" * 43]
    assert "client_secret" not in form


def test_code_exchange_rejects_invalid_pkce_verifier(monkeypatch):
    def unexpected_urlopen(*_args, **_kwargs):
        pytest.fail("invalid PKCE verifier must be rejected before network access")

    monkeypatch.setattr(auth_callback.urllib.request, "urlopen", unexpected_urlopen)

    with pytest.raises(auth_callback.HTTPException) as exc:
        auth_callback._exchange_code_with_keycloak(
            "auth-code", "https://am-dev.asrax.in/qa/ui/callback", "too-short"
        )

    assert exc.value.status_code == 400
