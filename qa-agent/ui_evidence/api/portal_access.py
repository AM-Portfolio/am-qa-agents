"""Authorization helpers for QA Portal / Corp Docs access roles."""

from __future__ import annotations

from typing import Iterable

# Keycloak realm roles that grant portal entry (am-realm).
QA_PORTAL_ACCESS_ROLES = frozenset(
    {
        "access-qa-portal",
        "qa_operator",
        "qa_admin",
        "am-admin",
        "admin",
    }
)

CORP_DOCS_ACCESS_ROLES = frozenset(
    {
        "access-corp-docs",
        "corp_admin",
        "am-admin",
        "admin",
    }
)


def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def parse_email_allowlist(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def has_any_role(user_roles: Iterable[str], required: Iterable[str]) -> bool:
    have = {r.strip() for r in user_roles if r and str(r).strip()}
    need = {r.strip() for r in required if r and str(r).strip()}
    return bool(have & need)


def authorize_portal_access(
    *,
    email: str | None,
    token_roles: Iterable[str],
    required_roles: Iterable[str],
    email_allowlist: Iterable[str],
    session_roles_on_allowlist: Iterable[str],
) -> list[str]:
    """Return effective portal roles or raise ValueError if denied.

    Access is granted when:
    1) JWT / Keycloak claims include a required role, or
    2) email is on the explicit allowlist (bootstrap for Central Login direct codes
       until full OIDC token exchange carries realm roles).
    """
    roles = [str(r) for r in token_roles if r]
    if has_any_role(roles, required_roles):
        return roles

    email_norm = normalize_email(email)
    allow = {normalize_email(e) for e in email_allowlist if e}
    if email_norm and email_norm in allow:
        extra = [str(r) for r in session_roles_on_allowlist if r]
        return list(dict.fromkeys([*roles, *extra]))

    raise ValueError(
        "Access denied: your AM account is not authorized for this portal. "
        "Ask an admin to grant the required Keycloak role."
    )
