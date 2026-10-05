"""Keycloak helpers for throwaway QA users (force-verify + disable)."""
from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


def _kc_config() -> dict[str, str] | None:
    url = (
        os.environ.get("KEYCLOAK_URL")
        or os.environ.get("KC_URL")
        or ""
    ).rstrip("/")
    realm = (
        os.environ.get("KEYCLOAK_REALM")
        or os.environ.get("KC_REALM")
        or ""
    ).strip()
    admin = (
        os.environ.get("KEYCLOAK_ADMIN")
        or os.environ.get("KEYCLOAK_ADMIN_USER")
        or os.environ.get("KC_ADMIN")
        or ""
    ).strip()
    password = (
        os.environ.get("KEYCLOAK_ADMIN_PASSWORD")
        or os.environ.get("KC_ADMIN_PASSWORD")
        or ""
    ).strip()
    if not (url and realm and admin and password):
        return None
    return {"url": url, "realm": realm, "admin": admin, "password": password}


def keycloak_configured() -> bool:
    return _kc_config() is not None


def _admin_token(cfg: dict[str, str]) -> str | None:
    token_url = f"{cfg['url']}/realms/master/protocol/openid-connect/token"
    # Some installs use /auth prefix
    candidates = [
        token_url,
        f"{cfg['url']}/auth/realms/master/protocol/openid-connect/token",
    ]
    data = {
        "grant_type": "password",
        "client_id": "admin-cli",
        "username": cfg["admin"],
        "password": cfg["password"],
    }
    with httpx.Client(timeout=20.0) as client:
        for url in candidates:
            try:
                resp = client.post(url, data=data)
            except httpx.HTTPError as exc:
                logger.warning("keycloak token request failed: %s", exc)
                continue
            if resp.status_code < 400:
                tok = (resp.json() or {}).get("access_token")
                if tok:
                    return str(tok)
    return None


def _admin_base(cfg: dict[str, str], token: str) -> str | None:
    """Detect whether admin API lives under /auth or root."""
    with httpx.Client(timeout=15.0) as client:
        for prefix in ("", "/auth"):
            base = f"{cfg['url']}{prefix}/admin/realms/{cfg['realm']}"
            resp = client.get(
                f"{base}/users?max=1",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code < 400:
                return base
    return None


def force_verify_email(*, email: str, user_id: str | None = None) -> dict[str, Any]:
    """Set emailVerified=true and clear requiredActions for a Keycloak user."""
    cfg = _kc_config()
    if not cfg:
        return {"ok": False, "reason": "keycloak_not_configured"}
    token = _admin_token(cfg)
    if not token:
        return {"ok": False, "reason": "keycloak_admin_token_failed"}
    admin_base = _admin_base(cfg, token)
    if not admin_base:
        return {"ok": False, "reason": "keycloak_admin_api_unreachable"}
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    with httpx.Client(timeout=20.0) as client:
        uid = user_id
        if not uid:
            resp = client.get(
                f"{admin_base}/users?email={quote(email)}&exact=true",
                headers=headers,
            )
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "reason": "find_user_failed",
                    "http_status": resp.status_code,
                }
            rows = resp.json() or []
            if not rows:
                return {"ok": False, "reason": "user_not_found"}
            uid = str(rows[0]["id"])
        get = client.get(f"{admin_base}/users/{uid}", headers=headers)
        if get.status_code >= 400:
            return {
                "ok": False,
                "reason": "get_user_failed",
                "http_status": get.status_code,
            }
        user = get.json()
        user["emailVerified"] = True
        user["requiredActions"] = []
        put = client.put(
            f"{admin_base}/users/{uid}",
            headers={**headers, "Content-Type": "application/json"},
            json=user,
        )
        return {
            "ok": put.status_code in (200, 204),
            "user_id": uid,
            "http_status": put.status_code,
        }


def disable_user(*, email: str, user_id: str | None = None) -> dict[str, Any]:
    """Disable throwaway user in Keycloak (cleanup fallback)."""
    cfg = _kc_config()
    if not cfg:
        return {"ok": False, "reason": "keycloak_not_configured"}
    token = _admin_token(cfg)
    if not token:
        return {"ok": False, "reason": "keycloak_admin_token_failed"}
    admin_base = _admin_base(cfg, token)
    if not admin_base:
        return {"ok": False, "reason": "keycloak_admin_api_unreachable"}
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    with httpx.Client(timeout=20.0) as client:
        uid = user_id
        if not uid:
            resp = client.get(
                f"{admin_base}/users?email={quote(email)}&exact=true",
                headers=headers,
            )
            if resp.status_code >= 400 or not (resp.json() or []):
                return {"ok": False, "reason": "user_not_found"}
            uid = str(resp.json()[0]["id"])
        get = client.get(f"{admin_base}/users/{uid}", headers=headers)
        if get.status_code >= 400:
            return {"ok": False, "reason": "get_user_failed"}
        user = get.json()
        user["enabled"] = False
        put = client.put(
            f"{admin_base}/users/{uid}",
            headers={**headers, "Content-Type": "application/json"},
            json=user,
        )
        return {
            "ok": put.status_code in (200, 204),
            "user_id": uid,
            "http_status": put.status_code,
        }
