"""Identity API scenario helpers for auth_user_module (prod Swagger ops)."""
from __future__ import annotations

from typing import Any


# Safe-to-call ops against prod (no account creation).
AUTH_API_SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "AUTH_API_HEALTH",
        "description": "Identity health / ready",
        "service": "am-identity",
        "tool_match": ["health", "ready", "root"],
        "safe": True,
    },
    {
        "id": "AUTH_API_LOGIN",
        "description": "Password login via /auth/login (uses SPT_AUTH_* creds)",
        "service": "am-identity",
        "tool_match": ["auth_login", "login"],
        "path_contains": "/auth/login",
        "method": "post",
        "safe": True,
        "uses_spt_auth_creds": True,
    },
    {
        "id": "AUTH_API_USERS_ME",
        "description": "GET current user after login",
        "service": "am-identity",
        "tool_match": ["users_me", "me"],
        "path_contains": "/users/me",
        "method": "get",
        "safe": True,
        "requires_auth": True,
    },
    {
        "id": "AUTH_API_FORGOT_SCHEMA",
        "description": "Discover forgot-password op from OpenAPI (call only if soft)",
        "service": "am-identity",
        "tool_match": ["forgot", "password_reset", "reset_password"],
        "safe": True,
        "discover_only": True,
    },
    {
        "id": "AUTH_API_REGISTER_SCHEMA",
        "description": "Discover register op from OpenAPI (no prod submit)",
        "service": "am-identity",
        "tool_match": ["register", "signup"],
        "safe": True,
        "discover_only": True,
    },
]


def resolve_tool_for_scenario(
    tools: list[dict[str, Any]], scenario: dict[str, Any]
) -> dict[str, Any] | None:
    """Pick best generated tool for a scenario."""
    path_contains = str(scenario.get("path_contains") or "").lower()
    method = str(scenario.get("method") or "").lower()
    matches = [str(m).lower() for m in (scenario.get("tool_match") or [])]
    scored: list[tuple[int, dict[str, Any]]] = []
    for t in tools:
        name = str(t.get("name") or "").lower()
        path = str(t.get("path") or "").lower()
        m = str(t.get("method") or "").lower()
        if method and m != method:
            continue
        score = 0
        if path_contains and path_contains in path:
            score += 10
        for hint in matches:
            if hint in name or hint in path:
                score += 3
        if score:
            scored.append((score, t))
    if not scored:
        return None
    scored.sort(key=lambda x: (-x[0], x[1].get("name") or ""))
    return scored[0][1]
