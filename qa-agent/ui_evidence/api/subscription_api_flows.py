"""Subscription-only API flow definitions (login prerequisite + subscription)."""
from __future__ import annotations

from typing import Any

SUBSCRIPTION_API_FLOWS: list[dict[str, Any]] = [
    {
        "id": "FLOW_SUBSCRIPTION_LOGIN",
        "title": "Login with SPT creds (JWT for subscription calls)",
        "gate": "prod_safe",
        "steps": [
            {
                "id": "login",
                "kind": "call_tool",
                "service": "am-identity",
                "path_contains": "/auth/login",
                "method": "post",
                "uses_spt_auth_creds": True,
                "capture_tokens": True,
            },
        ],
    },
    {
        "id": "FLOW_SUBSCRIPTION",
        "title": "Subscription plans / me / time-left fields",
        "gate": "prod_safe",
        "steps": [
            {
                "id": "sub_health",
                "kind": "call_tool",
                "service": "am-subscription",
                "path_contains": "/health",
                "method": "get",
                "optional_service": True,
            },
            {
                "id": "sub_plans",
                "kind": "call_tool",
                "service": "am-subscription",
                "tool_match": ["plan"],
                "method": "get",
                "optional_service": True,
                "auth": True,
            },
            {
                "id": "sub_me",
                "kind": "call_tool",
                "service": "am-subscription",
                "tool_match": ["subscription", "me", "current"],
                "method": "get",
                "optional_service": True,
                "auth": True,
                "note": "Expect trial/expires/time-left fields when OpenAPI is live",
            },
            {
                "id": "sub_ai_proxy",
                "kind": "raw_http",
                "service": "am-identity",
                "base_url_override": "https://am.asrax.in",
                "exact_path": "/ai/subscription/plans",
                "method": "get",
                "auth": True,
                "optional_service": True,
                "note": "gateway AI proxy fallback when subscription OpenAPI is HTML",
            },
        ],
    },
]
