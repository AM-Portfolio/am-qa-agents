import asyncio
import base64
import json
import time

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from specs.main import qa_portal_auth_callback, qa_portal_central_session


def _request(path: str, body: dict) -> Request:
    raw = json.dumps(body).encode()

    async def receive():
        return {"type": "http.request", "body": raw, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": [],
            "query_string": b"",
            "scheme": "https",
            "server": ("localhost", 443),
            "client": ("127.0.0.1", 1),
        },
        receive,
    )


def _unsigned_jwt(payload: dict) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{header}.{body}.sig"


def test_callback_rejects_mock_code_and_caller_claims_without_pkce():
    request = _request(
        "/api/v1/auth/callback",
        {
            "code": "mock_admin",
            "email": "attacker@example.com",
            "roles": ["access-qa-portal"],
        },
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(qa_portal_auth_callback(request))

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid PKCE verifier"


def test_central_session_accepts_am_dev_token_with_qa_role():
    token = _unsigned_jwt(
        {
            "iss": "https://auth.asrax.in/realms/am-dev-realm",
            "exp": int(time.time()) + 600,
            "email": "operator@asrax.in",
            "preferred_username": "operator",
            "realm_access": {"roles": ["qa_operator"]},
        }
    )
    result = asyncio.run(
        qa_portal_central_session(
            _request(
                "/api/v1/auth/central-session",
                {"access_token": token, "state": "/ui-flows"},
            )
        )
    )
    assert result["access_token"] == token
    assert result["state"] == "/ui-flows"
    assert "qa_operator" in result["user"]["roles"]


def test_central_session_rejects_untrusted_issuer():
    token = _unsigned_jwt(
        {
            "iss": "https://evil.example/realms/x",
            "exp": int(time.time()) + 600,
            "email": "operator@asrax.in",
            "realm_access": {"roles": ["qa_operator"]},
        }
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            qa_portal_central_session(
                _request("/api/v1/auth/central-session", {"access_token": token})
            )
        )
    assert exc.value.status_code == 401
    assert "Untrusted" in str(exc.value.detail)


def test_central_handoff_mint_and_redeem():
    from specs.main import qa_portal_central_handoff_mint

    token = _unsigned_jwt(
        {
            "iss": "https://auth.asrax.in/realms/am-dev-realm",
            "exp": int(time.time()) + 600,
            "email": "operator@asrax.in",
            "preferred_username": "operator",
            "realm_access": {"roles": ["access-qa-portal"]},
        }
    )
    minted = asyncio.run(
        qa_portal_central_handoff_mint(
            _request(
                "/api/v1/auth/central-handoff-mint",
                {"access_token": token},
            )
        )
    )
    assert minted["handoff"]
    redeemed = asyncio.run(
        qa_portal_central_session(
            _request(
                "/api/v1/auth/central-session",
                {"handoff": minted["handoff"], "state": "/ui-flows"},
            )
        )
    )
    assert redeemed["access_token"] == token
    assert "access-qa-portal" in redeemed["user"]["roles"]
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            qa_portal_central_session(
                _request(
                    "/api/v1/auth/central-session",
                    {"handoff": minted["handoff"]},
                )
            )
        )
    assert exc.value.status_code == 401
