"""Resolve dig/dev Mongo URI for local invent runs (not localhost)."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

# Contabo TCP gateway for dig Mongo (am-infra/docs/tcp_gateway_guide.md)
_DIG_PUBLIC_HOST = "mongodb-dev.asrax.in"
_DIG_PUBLIC_PORT = "8895"
_DIG_DB_DEFAULT = "am_qa_agent_dev"


def _asrax_home() -> Path:
    return Path(os.getenv("ASRAX_HOME") or Path.home() / ".asrax")


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k:
            out[k] = v
    return out


def load_asrax_mongo_vars() -> dict[str, str]:
    """Merge ~/.asrax credentials overlays for Mongo (no secret logging)."""
    home = _asrax_home()
    merged: dict[str, str] = {}
    for name in (
        "credentials.env",
        "credentials.vault.env",
        "credentials.d/dev-infra-stores.env",
        "credentials.d/dev.env",
        "credentials.d/mongo.env",
        "credentials.d/qa-agent.env",
    ):
        merged.update(_parse_env_file(home / name))
    return merged


def build_mongo_uri(
    *,
    host: str,
    port: str,
    user: str,
    password: str,
    auth_source: str = "admin",
    direct: bool = True,
) -> str:
    user_q = quote_plus(user)
    pass_q = quote_plus(password)
    qs = f"authSource={auth_source}"
    if direct:
        qs += "&directConnection=true"
    return f"mongodb://{user_q}:{pass_q}@{host}:{port}/?{qs}"


def resolve_dev_mongo(*, force: bool = False) -> dict[str, Any]:
    """
    Ensure MONGO_URI / MONGO_DATABASE point at dig Mongo for local runs.

    Order:
    1. Existing MONGO_URI / MONGODB_URI (unless force)
    2. Build from MONGO_HOST/PORT/USER/PASSWORD env
    3. Build from ~/.asrax credentials.d dig stores + public dig TCP host:8895
    """
    if os.getenv("KUBERNETES_SERVICE_HOST") and not force:
        return {
            "ok": True,
            "source": "in_cluster",
            "uri_set": bool(os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")),
            "database": os.getenv("MONGO_DATABASE") or _DIG_DB_DEFAULT,
        }

    existing = (os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or "").strip()
    allow_local = os.getenv("QA_MONGO_ALLOW_LOCAL", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if existing and not force:
        is_loopback = ("localhost" in existing) or ("127.0.0.1" in existing)
        if (not is_loopback) or allow_local:
            os.environ.setdefault(
                "MONGO_DATABASE", os.getenv("MONGO_DATABASE") or _DIG_DB_DEFAULT
            )
            if not os.getenv("MONGO_URI") and os.getenv("MONGODB_URI"):
                os.environ["MONGO_URI"] = os.environ["MONGODB_URI"]
            return {
                "ok": True,
                "source": "env_local" if is_loopback else "env",
                "uri_set": True,
                "host_hint": _host_hint(existing),
                "database": os.getenv("MONGO_DATABASE") or _DIG_DB_DEFAULT,
            }

    # Prefer process env pieces, then asrax overlays
    overlays = load_asrax_mongo_vars()
    user = (
        os.getenv("MONGO_USER")
        or os.getenv("MONGO_USERNAME")
        or overlays.get("MONGO_USER")
        or overlays.get("MONGO_USERNAME")
        or "admin"
    )
    password = (
        os.getenv("MONGO_PASSWORD")
        or overlays.get("MONGO_PASSWORD")
        or ""
    )
    # Laptop → Contabo dig TCP gateway (not Kind in-cluster DNS)
    host = (
        os.getenv("MONGO_HOST_PUBLIC")
        or os.getenv("QA_MONGO_HOST")
        or _DIG_PUBLIC_HOST
    )
    port = (
        os.getenv("MONGO_PORT_PUBLIC")
        or os.getenv("QA_MONGO_PORT")
        or _DIG_PUBLIC_PORT
    )
    # Allow override from dig.env only when explicitly targeting kind DNS
    if os.getenv("QA_MONGO_USE_KIND_DNS", "").lower() in {"1", "true", "yes"}:
        host = os.getenv("MONGO_HOST") or overlays.get("MONGO_HOST") or host
        port = os.getenv("MONGO_PORT") or overlays.get("MONGO_PORT") or port

    db = (
        os.getenv("MONGO_DATABASE")
        or overlays.get("MONGO_DATABASE")
        or overlays.get("QA_AGENT_MONGO_DATABASE")
        or _DIG_DB_DEFAULT
    )

    if not password:
        return {
            "ok": False,
            "source": "missing_password",
            "uri_set": False,
            "error": (
                "MONGO_PASSWORD not set; put it in ~/.asrax/credentials.d/dev-infra-stores.env "
                "or export MONGO_URI for dig Mongo"
            ),
            "host_hint": f"{host}:{port}",
            "database": db,
        }

    uri = build_mongo_uri(host=host, port=str(port), user=user, password=password)
    os.environ["MONGO_URI"] = uri
    os.environ["MONGODB_URI"] = uri
    os.environ["MONGO_DATABASE"] = db
    os.environ.setdefault("QA_SCENARIO_BANK_BACKEND", "mongo")
    return {
        "ok": True,
        "source": "asrax_credentials_d",
        "uri_set": True,
        "host_hint": f"{host}:{port}",
        "database": db,
        "user": user,
    }


def _host_hint(uri: str) -> str:
    try:
        # mongodb://user:pass@host:port/...
        after = uri.split("@", 1)[-1]
        return after.split("/", 1)[0]
    except Exception:  # noqa: BLE001
        return "(set)"


def ensure_dev_mongo_for_local_invent() -> dict[str, Any]:
    """Call before invent/repo when running on a laptop against dig."""
    # Prefer dig mongo even if .env left MONGO_URI as localhost — unless
    # QA_MONGO_ALLOW_LOCAL=1 (laptop pilot when dig TCP gateway is down).
    allow_local = os.getenv("QA_MONGO_ALLOW_LOCAL", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    existing = (os.getenv("MONGO_URI") or "").strip()
    force = (not allow_local) and (
        (not existing) or ("localhost" in existing) or ("127.0.0.1" in existing)
    )
    result = resolve_dev_mongo(force=force)
    if result.get("ok"):
        logger.info(
            "scenario_bank mongo source=%s host=%s db=%s",
            result.get("source"),
            result.get("host_hint"),
            result.get("database"),
        )
    else:
        logger.warning("scenario_bank dig mongo resolve failed: %s", result.get("error"))
    return result


def try_local_mongo_fallback(port: int = 27018) -> dict[str, Any]:
    """Use a local Docker Mongo when dig TCP (8895) is unreachable."""
    uri = f"mongodb://127.0.0.1:{int(port)}/?directConnection=true"
    db = os.getenv("MONGO_DATABASE") or _DIG_DB_DEFAULT
    try:
        from pymongo import MongoClient

        client = MongoClient(uri, serverSelectionTimeoutMS=4000)
        client.admin.command("ping")
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "source": "local_fallback",
            "uri_set": False,
            "error": str(exc),
            "host_hint": f"127.0.0.1:{port}",
            "database": db,
        }
    os.environ["MONGO_URI"] = uri
    os.environ["MONGODB_URI"] = uri
    os.environ["MONGO_DATABASE"] = db
    os.environ["QA_SCENARIO_BANK_BACKEND"] = "mongo"
    os.environ["QA_MONGO_ALLOW_LOCAL"] = "1"
    return {
        "ok": True,
        "source": "local_fallback",
        "uri_set": True,
        "host_hint": f"127.0.0.1:{port}",
        "database": db,
    }
