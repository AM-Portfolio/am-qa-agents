"""Named QA credentials — encrypted at rest; list/get never return secrets."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from specs.config import settings

_LOCK = threading.Lock()
_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,63}$")
_KINDS = frozenset(
    {
        "identity_login",
        "bearer_token",
        "http_basic",
        "llm_api_key",
        "api_key_header",
    }
)
_ENVS = frozenset({"prod", "preprod", "dev"})

# Catalog for portal "Add credential" picker (extensible for third-party apps).
CREDENTIAL_APPS: list[dict[str, Any]] = [
    {
        "id": "asrax-identity",
        "kind": "identity_login",
        "title": "ASRAX Identity login",
        "auth_label": "Username / password",
        "description": "SPT / identity JWT login for API flows",
        "enabled": True,
    },
    {
        "id": "http-basic",
        "kind": "http_basic",
        "title": "HTTP Basic Auth",
        "auth_label": "Basic Auth",
        "description": "Username + password for Basic challenges",
        "enabled": True,
    },
    {
        "id": "bearer-token",
        "kind": "bearer_token",
        "title": "Bearer token",
        "auth_label": "Header Auth",
        "description": "Static Authorization Bearer token",
        "enabled": True,
    },
    {
        "id": "llm-api-key",
        "kind": "llm_api_key",
        "title": "LLM API key",
        "auth_label": "API Key",
        "description": "LiteLLM / OpenAI-compatible master key",
        "enabled": True,
    },
    {
        "id": "api-key-header",
        "kind": "api_key_header",
        "title": "Third-party API key",
        "auth_label": "Header Auth",
        "description": "Generic API key for future third-party connectors",
        "enabled": True,
    },
]


def list_credential_apps() -> list[dict[str, Any]]:
    return [dict(a) for a in CREDENTIAL_APPS]


class CredentialStoreError(ValueError):
    pass


def _store_path() -> Path:
    return Path(settings.data_dir) / "qa_credentials.json"


def _fernet():
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:  # pragma: no cover
        raise CredentialStoreError(
            "cryptography package required for credential store"
        ) from exc
    raw = (
        os.environ.get("QA_CREDENTIALS_KEY")
        or os.environ.get("SPT_CREDENTIALS_KEY")
        or getattr(settings, "qa_credentials_key", None)
        or ""
    ).strip()
    if not raw:
        # Stable per data_dir so restarts keep decrypting (not for multi-tenant).
        raw = f"qa-creds:{settings.data_dir}:spt"
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def _encrypt(secret: str) -> str:
    return _fernet().encrypt(secret.encode("utf-8")).decode("ascii")


def _decrypt(blob: str) -> str:
    return _fernet().decrypt(blob.encode("ascii")).decode("utf-8")


def _empty() -> dict[str, Any]:
    return {"version": 1, "credentials": {}}


def _load() -> dict[str, Any]:
    path = _store_path()
    if not path.is_file():
        return _empty()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty()
    if not isinstance(raw, dict):
        return _empty()
    creds = raw.get("credentials")
    if not isinstance(creds, dict):
        creds = {}
    return {"version": int(raw.get("version") or 1), "credentials": creds}


def _save(data: dict[str, Any]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    with _LOCK:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)


def _auth_label(kind: str) -> str:
    for app in CREDENTIAL_APPS:
        if app.get("kind") == kind:
            return str(app.get("auth_label") or kind)
    return kind


def _public(rec: dict[str, Any]) -> dict[str, Any]:
    kind = str(rec.get("kind") or "identity_login")
    return {
        "id": rec.get("id"),
        "name": rec.get("name"),
        "kind": kind,
        "auth_label": _auth_label(kind),
        "env": rec.get("env"),
        "username": rec.get("username") or "",
        "base_url": rec.get("base_url") or "",
        "has_secret": bool(rec.get("secret_enc")),
        "created_at": rec.get("created_at") or rec.get("updated_at"),
        "updated_at": rec.get("updated_at"),
        "scope": rec.get("scope") or "personal",
    }


def validate_id(cid: str) -> str:
    s = (cid or "").strip()
    if not _ID_RE.match(s):
        raise CredentialStoreError(
            f"Invalid credential id {cid!r}: letters/numbers/_/-; start with letter"
        )
    return s


def list_credentials(*, env: str | None = None, kind: str | None = None) -> list[dict[str, Any]]:
    data = _load()
    out: list[dict[str, Any]] = []
    for rec in (data.get("credentials") or {}).values():
        if not isinstance(rec, dict):
            continue
        if env and str(rec.get("env") or "") != env:
            continue
        if kind and str(rec.get("kind") or "") != kind:
            continue
        out.append(_public(rec))
    out.sort(key=lambda r: (str(r.get("env") or ""), str(r.get("name") or "")))
    return out


def get_credential_public(cid: str) -> dict[str, Any] | None:
    data = _load()
    rec = (data.get("credentials") or {}).get(cid)
    if not isinstance(rec, dict):
        return None
    return _public(rec)


def resolve_credential(cid: str) -> dict[str, Any] | None:
    """Internal: decrypted secrets for runners only."""
    data = _load()
    rec = (data.get("credentials") or {}).get(cid)
    if not isinstance(rec, dict):
        return None
    secret = ""
    enc = rec.get("secret_enc")
    if enc:
        try:
            secret = _decrypt(str(enc))
        except Exception:  # noqa: BLE001
            raise CredentialStoreError(f"failed to decrypt credential {cid}")
    kind = str(rec.get("kind") or "identity_login")
    out: dict[str, Any] = {
        "id": rec.get("id"),
        "name": rec.get("name"),
        "kind": kind,
        "env": rec.get("env"),
        "username": rec.get("username") or "",
        "base_url": rec.get("base_url") or "",
    }
    if kind in {"bearer_token", "llm_api_key", "api_key_header"}:
        out["token"] = secret
        out["password"] = ""
    else:
        out["password"] = secret
    return out


def upsert_credential(
    *,
    id: str | None = None,
    name: str,
    kind: str = "identity_login",
    env: str = "prod",
    username: str = "",
    password: str | None = None,
    token: str | None = None,
    base_url: str = "",
) -> dict[str, Any]:
    kind_n = (kind or "identity_login").strip()
    env_n = (env or "prod").strip().lower()
    if env_n == "dig":
        env_n = "dev"
    if kind_n not in _KINDS:
        raise CredentialStoreError(f"unsupported kind {kind_n!r}")
    if env_n not in _ENVS:
        raise CredentialStoreError(f"unsupported env {env_n!r}")
    name_s = (name or "").strip()
    if not name_s:
        raise CredentialStoreError("name required")

    cid = validate_id(id) if id else validate_id(
        f"cred_{uuid.uuid4().hex[:12]}"
    )
    data = _load()
    creds = dict(data.get("credentials") or {})
    existing = creds.get(cid) if isinstance(creds.get(cid), dict) else {}

    secret_plain = ""
    token_kinds = {"bearer_token", "llm_api_key", "api_key_header"}
    if kind_n in token_kinds:
        secret_plain = (token if token is not None else "") or ""
        if not secret_plain and existing.get("secret_enc"):
            secret_enc = existing["secret_enc"]
        elif not secret_plain:
            raise CredentialStoreError(f"token required for {kind_n}")
        else:
            secret_enc = _encrypt(secret_plain)
    else:
        secret_plain = (password if password is not None else "") or ""
        if not secret_plain and existing.get("secret_enc"):
            secret_enc = existing["secret_enc"]
        elif not secret_plain:
            raise CredentialStoreError("password required for identity_login/http_basic")
        else:
            secret_enc = _encrypt(secret_plain)

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rec = {
        "id": cid,
        "name": name_s,
        "kind": kind_n,
        "env": env_n,
        "username": (username or existing.get("username") or "").strip(),
        "base_url": (base_url or existing.get("base_url") or "").strip(),
        "secret_enc": secret_enc,
        "scope": existing.get("scope") or "personal",
        "created_at": existing.get("created_at") or now,
        "updated_at": now,
    }
    creds[cid] = rec
    data["credentials"] = creds
    _save(data)
    return _public(rec)


def delete_credential(cid: str) -> bool:
    data = _load()
    creds = dict(data.get("credentials") or {})
    if cid not in creds:
        return False
    del creds[cid]
    data["credentials"] = creds
    _save(data)
    return True


def seed_from_spt_env() -> list[dict[str, Any]]:
    """Idempotent seed of SPT operator login into the store."""
    user = (
        os.environ.get("SPT_AUTH_USERNAME") or settings.spt_auth_username or ""
    ).strip()
    password = (
        os.environ.get("SPT_AUTH_PASSWORD") or settings.spt_auth_password or ""
    )
    if not user or not password:
        return []
    env = (settings.app_env or settings.default_environment or "prod").strip().lower()
    if env == "dig":
        env = "dev"
    if env not in _ENVS:
        env = "prod"
    cid = f"spt-login-{env}"
    existing = get_credential_public(cid)
    if existing and existing.get("has_secret"):
        return [existing]
    return [
        upsert_credential(
            id=cid,
            name=f"SPT login ({env})",
            kind="identity_login",
            env=env,
            username=user,
            password=str(password),
            base_url=(settings.spt_identity_url or "").strip(),
        )
    ]


def resolve_login_pair(
    *,
    credential_id: str | None = None,
    env: str | None = None,
) -> tuple[str, str, str | None]:
    """Username/password/(optional identity base) for pack/suite runners.

    Prefer ``credential_id``, else seeded ``spt-login-{env}``, else SPT_* env.
    """
    if credential_id:
        rec = resolve_credential(credential_id)
        if rec:
            return (
                str(rec.get("username") or ""),
                str(rec.get("password") or rec.get("token") or ""),
                str(rec.get("base_url") or "") or None,
            )
    env_n = (env or settings.app_env or settings.default_environment or "prod").strip().lower()
    if env_n == "dig":
        env_n = "dev"
    seed_from_spt_env()
    seeded = get_credential_public(f"spt-login-{env_n}")
    if seeded and seeded.get("has_secret"):
        rec = resolve_credential(str(seeded["id"]))
        if rec:
            return (
                str(rec.get("username") or ""),
                str(rec.get("password") or ""),
                str(rec.get("base_url") or "") or None,
            )
    user = (
        os.environ.get("SPT_AUTH_USERNAME") or settings.spt_auth_username or ""
    ).strip()
    password = str(
        os.environ.get("SPT_AUTH_PASSWORD") or settings.spt_auth_password or ""
    )
    return user, password, None
