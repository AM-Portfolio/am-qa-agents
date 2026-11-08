from __future__ import annotations

import os
from typing import Any

from specs import env_urls
from specs.config import settings
from specs.security.identity_client import jwt_sub, login_identity


def sanitize_auth_env(auth: dict[str, Any] | None) -> dict[str, Any]:
    """Safe auth metadata for UI / run storage (no token or password)."""
    src = dict(auth or {})
    out: dict[str, Any] = {}
    for key in ("username", "user_id", "identity_url"):
        val = src.get(key)
        if val:
            out[key] = val
    if src.get("token") or src.get("password"):
        out["authenticated"] = True
    elif out.get("username"):
        out["authenticated"] = False
    return out


def resolve_identity_url(config: dict[str, Any], auth: dict[str, Any]) -> str:
    """Prefer explicit auth identity_url; else match the run's environment (not APP_ENV).

    Laptop .env often pins SPT_IDENTITY_URL=prod while Specs runs target dig/dev —
    using the global pin causes Invalid user credentials against the wrong realm.
    """
    explicit = str(auth.get("identity_url") or "").strip()
    if explicit:
        return explicit
    run_env = str(config.get("environment") or "").strip()
    if run_env and env_urls.normalize_env(run_env):
        return env_urls.identity_url_for_env(run_env)
    return str(
        os.environ.get("SPT_IDENTITY_URL")
        or settings.spt_identity_url
        or env_urls.identity_url_for_env(settings.default_environment)
        or ""
    ).strip()


async def ensure_auth_env(config: dict[str, Any]) -> dict[str, Any]:
    """Fetch JWT from am-identity when username/password are configured."""
    payloads = dict(config.get("payloads") or {})
    auth = dict(payloads.get("auth_env") or {})

    if auth.get("token") or os.environ.get("SPT_AUTH_TOKEN"):
        if not auth.get("username"):
            auth["username"] = (
                os.environ.get("SPT_AUTH_USERNAME") or settings.spt_auth_username or ""
            )
        token = str(auth.get("token") or os.environ.get("SPT_AUTH_TOKEN") or "")
        if token and not auth.get("user_id"):
            sub = jwt_sub(token)
            if sub:
                auth["user_id"] = sub
        payloads["auth_env"] = auth
        config["payloads"] = payloads
        return config

    # Named credential from encrypted QA store (suites / pack runners / flows).
    cred_id = str(
        auth.get("credential_id") or config.get("credential_id") or ""
    ).strip()
    if cred_id:
        from specs.security.credential_store import resolve_credential

        rec = resolve_credential(cred_id)
        if rec:
            if rec.get("kind") == "bearer_token" and rec.get("token"):
                auth["token"] = str(rec["token"])
                auth["username"] = str(rec.get("username") or auth.get("username") or "")
                if rec.get("base_url"):
                    auth["identity_url"] = str(rec["base_url"])
                auth["credential_id"] = cred_id
                payloads["auth_env"] = auth
                config["payloads"] = payloads
                if auth.get("token") and not auth.get("user_id"):
                    sub = jwt_sub(str(auth["token"]))
                    if sub:
                        auth["user_id"] = sub
                        payloads["auth_env"] = auth
                        config["payloads"] = payloads
                return config
            auth["username"] = str(rec.get("username") or "")
            auth["password"] = str(rec.get("password") or "")
            if rec.get("base_url"):
                auth["identity_url"] = str(rec["base_url"])
            auth["credential_id"] = cred_id

    # Prefer a coherent credential pair. Seed/Postman auth_env often has username
    # only (e.g. default ssd2658@…) — pairing that with SPT_AUTH_PASSWORD causes
    # Keycloak invalid_grant. Use explicit payload password only when both set.
    env_user = str(
        os.environ.get("SPT_AUTH_USERNAME") or settings.spt_auth_username or ""
    ).strip()
    env_pass = str(
        os.environ.get("SPT_AUTH_PASSWORD") or settings.spt_auth_password or ""
    )
    auth_user = str(auth.get("username") or "").strip()
    auth_pass = str(auth.get("password") or "")
    if auth_user and auth_pass:
        username, password = auth_user, auth_pass
    elif env_user and env_pass:
        username, password = env_user, env_pass
    else:
        username = auth_user or env_user
        password = auth_pass or env_pass
    identity_url = resolve_identity_url(config, auth)

    if not username or not password or not identity_url:
        payloads["auth_env"] = auth
        config["payloads"] = payloads
        return config

    token_body = await login_identity(identity_url, username, password)
    token = str(token_body["access_token"])
    auth["token"] = token
    auth["username"] = username
    auth["identity_url"] = identity_url
    sub = jwt_sub(token)
    if sub:
        auth["user_id"] = sub
    payloads["auth_env"] = auth
    config["payloads"] = payloads
    return config
