import asyncio
import json

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from specs.main import qa_portal_auth_callback


def test_callback_rejects_mock_code_and_caller_claims_without_pkce():
    body = json.dumps(
        {
            "code": "mock_admin",
            "email": "attacker@example.com",
            "roles": ["access-qa-portal"],
        }
    ).encode()

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/callback",
            "headers": [],
            "query_string": b"",
            "scheme": "https",
            "server": ("localhost", 443),
            "client": ("127.0.0.1", 1),
        },
        receive,
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(qa_portal_auth_callback(request))

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid PKCE verifier"
