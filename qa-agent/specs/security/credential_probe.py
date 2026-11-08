"""Live connectivity probes for credentials / resource connect."""
from __future__ import annotations

import socket
import time
from typing import Any
from urllib.parse import urlparse

from specs.security.credential_store import (
    get_credential_public,
    list_credentials,
    resolve_credential,
)


def probe_credential(cid: str) -> dict[str, Any]:
    pub = get_credential_public(cid)
    if not pub:
        return {
            "id": cid,
            "ok": False,
            "status": "missing",
            "message": "credential not found",
        }
    try:
        rec = resolve_credential(cid)
    except Exception as exc:  # noqa: BLE001
        return {
            "id": cid,
            "ok": False,
            "status": "error",
            "message": f"decrypt failed: {exc}",
            "kind": pub.get("kind"),
            "app_id": pub.get("app_id"),
        }
    if not rec:
        return {
            "id": cid,
            "ok": False,
            "status": "missing",
            "message": "credential not found",
        }

    kind = str(rec.get("kind") or "")
    t0 = time.perf_counter()
    try:
        if kind == "grafana_token":
            result = _probe_grafana(rec)
        elif kind == "prometheus_endpoint":
            result = _probe_prometheus(rec)
        elif kind == "cliq_webhook":
            result = _probe_cliq(rec)
        elif kind == "temporal_endpoint":
            result = _probe_temporal(rec)
        elif kind in {"identity_login", "http_basic"}:
            result = _probe_http_base(rec, basic=True)
        elif kind in {"bearer_token", "llm_api_key", "api_key_header"}:
            result = _probe_http_base(rec, bearer=True)
        else:
            result = {
                "ok": bool(rec.get("token") or rec.get("password") or rec.get("base_url")),
                "status": "stored",
                "message": "saved locally (no live probe for this kind)",
            }
    except Exception as exc:  # noqa: BLE001
        result = {"ok": False, "status": "error", "message": str(exc)[:240]}

    ms = round((time.perf_counter() - t0) * 1000, 1)
    return {
        "id": cid,
        "name": pub.get("name"),
        "kind": kind,
        "app_id": pub.get("app_id"),
        "env": pub.get("env"),
        "latency_ms": ms,
        **result,
    }


def probe_all(*, env: str | None = None) -> dict[str, Any]:
    rows = list_credentials(env=env)
    results = [probe_credential(str(r["id"])) for r in rows]
    ok_n = sum(1 for r in results if r.get("ok"))
    return {
        "results": results,
        "count": len(results),
        "ok_count": ok_n,
        "fail_count": len(results) - ok_n,
    }


def _httpx():
    import httpx

    return httpx


def _probe_grafana(rec: dict[str, Any]) -> dict[str, Any]:
    base = str(rec.get("base_url") or "").rstrip("/")
    token = str(rec.get("token") or "").strip()
    if not base:
        return {"ok": False, "status": "misconfigured", "message": "base_url required"}
    if not token:
        return {"ok": False, "status": "misconfigured", "message": "token required"}
    httpx = _httpx()
    url = f"{base}/api/health"
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=8.0, follow_redirects=True) as client:
        resp = client.get(url, headers=headers)
        if resp.status_code < 400:
            return {
                "ok": True,
                "status": "connected",
                "message": f"Grafana health HTTP {resp.status_code}",
            }
        # Some Grafana installs need org endpoint
        resp2 = client.get(f"{base}/api/org", headers=headers)
        if resp2.status_code < 400:
            return {
                "ok": True,
                "status": "connected",
                "message": f"Grafana org HTTP {resp2.status_code}",
            }
        return {
            "ok": False,
            "status": "unreachable",
            "message": f"Grafana HTTP {resp.status_code}/{resp2.status_code}",
        }


def _probe_prometheus(rec: dict[str, Any]) -> dict[str, Any]:
    base = str(rec.get("base_url") or "").rstrip("/")
    if not base:
        return {"ok": False, "status": "misconfigured", "message": "base_url required"}
    httpx = _httpx()
    headers = {}
    token = str(rec.get("token") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    candidates = [
        f"{base}/-/healthy",
        f"{base}/api/v1/status/buildinfo",
        f"{base}/api/v1/query?query=up",
    ]
    with httpx.Client(timeout=6.0, follow_redirects=True) as client:
        last = "no response"
        for url in candidates:
            try:
                resp = client.get(url, headers=headers)
                last = f"HTTP {resp.status_code}"
                if resp.status_code < 400:
                    return {
                        "ok": True,
                        "status": "connected",
                        "message": f"Prometheus {last}",
                    }
            except Exception as exc:  # noqa: BLE001
                last = str(exc)[:160]
        return {"ok": False, "status": "unreachable", "message": last}


def _probe_cliq(rec: dict[str, Any]) -> dict[str, Any]:
    wh = str(
        rec.get("webhook_url") or rec.get("token") or rec.get("base_url") or ""
    ).strip()
    if not wh:
        return {"ok": False, "status": "misconfigured", "message": "webhook URL required"}
    parsed = urlparse(wh)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"ok": False, "status": "misconfigured", "message": "invalid webhook URL"}
    httpx = _httpx()
    with httpx.Client(timeout=8.0, follow_redirects=True) as client:
        # Cliq webhooks are POST-only; GET/HEAD often 405 — treat as reachable.
        try:
            resp = client.get(wh)
            if resp.status_code in {200, 204, 400, 401, 403, 404, 405, 415}:
                return {
                    "ok": True,
                    "status": "connected",
                    "message": f"Webhook reachable (HTTP {resp.status_code})",
                }
            return {
                "ok": False,
                "status": "unreachable",
                "message": f"Webhook HTTP {resp.status_code}",
            }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "status": "unreachable", "message": str(exc)[:200]}


def _probe_temporal(rec: dict[str, Any]) -> dict[str, Any]:
    addr = str(rec.get("base_url") or "").strip()
    if not addr:
        return {"ok": False, "status": "misconfigured", "message": "address required"}
    # UI / https URL — HTTP probe
    if addr.startswith("http://") or addr.startswith("https://"):
        httpx = _httpx()
        with httpx.Client(timeout=8.0, follow_redirects=True) as client:
            resp = client.get(addr)
            if resp.status_code < 500:
                return {
                    "ok": True,
                    "status": "connected",
                    "message": f"Temporal UI HTTP {resp.status_code}",
                }
            return {
                "ok": False,
                "status": "unreachable",
                "message": f"Temporal UI HTTP {resp.status_code}",
            }
    # host:port gRPC frontend
    host = addr
    port = 7233
    if ":" in addr.rsplit("@", 1)[-1]:
        host, _, port_s = addr.rpartition(":")
        try:
            port = int(port_s)
        except ValueError:
            port = 7233
    try:
        with socket.create_connection((host, port), timeout=5.0):
            return {
                "ok": True,
                "status": "connected",
                "message": f"TCP {host}:{port} open",
            }
    except OSError as exc:
        return {"ok": False, "status": "unreachable", "message": str(exc)[:200]}


def _probe_http_base(
    rec: dict[str, Any],
    *,
    basic: bool = False,
    bearer: bool = False,
) -> dict[str, Any]:
    base = str(rec.get("base_url") or "").rstrip("/")
    if not base:
        has = bool(rec.get("password") or rec.get("token") or rec.get("username"))
        return {
            "ok": has,
            "status": "stored" if has else "misconfigured",
            "message": "saved locally (no base_url to probe)" if has else "missing secret",
        }
    httpx = _httpx()
    headers = {}
    auth = None
    if bearer and rec.get("token"):
        headers["Authorization"] = f"Bearer {rec['token']}"
    if basic and rec.get("username"):
        auth = (str(rec.get("username")), str(rec.get("password") or ""))
    with httpx.Client(timeout=6.0, follow_redirects=True) as client:
        resp = client.get(base, headers=headers, auth=auth)
        if resp.status_code < 500:
            return {
                "ok": True,
                "status": "connected",
                "message": f"HTTP {resp.status_code}",
            }
        return {
            "ok": False,
            "status": "unreachable",
            "message": f"HTTP {resp.status_code}",
        }
