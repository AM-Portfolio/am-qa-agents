from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlencode

from specs.config import settings

# Wide pad so sparse post-run points still land in the visible window.
_PAD_BEFORE_MIN = 30
_PAD_AFTER_MIN = 30


def _ms(iso: str | None) -> int:
    if not iso:
        return int(datetime.now(timezone.utc).timestamp() * 1000)
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except ValueError:
        return int(datetime.now(timezone.utc).timestamp() * 1000)


def _grafana_base(*, env: str | None = None) -> str:
    try:
        from specs.security.credential_store import resolve_grafana_base

        return resolve_grafana_base(env=env)
    except Exception:  # noqa: BLE001
        return (settings.grafana_public_url or "").rstrip("/")


def _range_ms(
    started_at: str | None,
    finished_at: str | None,
) -> tuple[int, int]:
    from_ms = _ms(started_at) - _PAD_BEFORE_MIN * 60_000
    to_ms = _ms(finished_at or started_at) + _PAD_AFTER_MIN * 60_000
    if to_ms <= from_ms:
        to_ms = from_ms + 60 * 60_000
    return from_ms, to_ms


def grafana_run_url(
    *,
    service: str | None = None,
    environment: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    run_id: str | None = None,
    env: str | None = None,
) -> str:
    """Deep-link the SPT dashboard locked to one run (no manual Grafana filters)."""
    base = _grafana_base(env=env or environment)
    if not base:
        return ""
    uid = settings.grafana_k6_dashboard_uid
    from_ms, to_ms = _range_ms(started_at, finished_at)

    params: dict[str, str] = {
        "orgId": "1",
        "from": str(from_ms),
        "to": str(to_ms),
        # Always set filters so Grafana never prompts "configure".
        "var-service": service or "All",
        "var-environment": environment or "All",
        "var-run_id": run_id or "All",
        "var-api_id": "All",
    }
    return f"{base}/d/{uid}/spt-load-testing?{urlencode(params)}"


def grafana_embed_url(**kwargs) -> str:
    url = grafana_run_url(**kwargs)
    if not url:
        return ""
    return url + "&kiosk=tv"


def grafana_tempo_explore_url(
    trace_id: str | None,
    *,
    started_at: str | None = None,
    finished_at: str | None = None,
    env: str | None = None,
) -> str:
    """Grafana Explore → Tempo TraceQL by OTEL trace id."""
    tid = (trace_id or "").strip()
    if not tid:
        return ""
    base = _grafana_base(env=env)
    if not base:
        return ""
    uid = (os.getenv("GRAFANA_TEMPO_DATASOURCE_UID") or "tempo").strip() or "tempo"
    org = (os.getenv("GRAFANA_ORG_ID") or "1").strip() or "1"
    from_ms, to_ms = _range_ms(started_at, finished_at)
    panes = {
        "trace": {
            "datasource": uid,
            "queries": [
                {
                    "refId": "A",
                    "datasource": {"type": "tempo", "uid": uid},
                    "queryType": "traceql",
                    "query": tid,
                }
            ],
            "range": {"from": str(from_ms), "to": str(to_ms)},
        }
    }
    encoded = quote(json.dumps(panes, separators=(",", ":")))
    return f"{base}/explore?orgId={org}&panes={encoded}&schemaVersion=1"


def grafana_loki_explore_url(
    trace_id: str | None,
    *,
    correlation_id: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    env: str | None = None,
) -> str:
    """Grafana Explore → Loki LogQL containing trace/correlation id."""
    needle = (trace_id or correlation_id or "").strip()
    if not needle:
        return ""
    base = _grafana_base(env=env)
    if not base:
        return ""
    uid = (os.getenv("GRAFANA_LOKI_DATASOURCE_UID") or "loki").strip() or "loki"
    org = (os.getenv("GRAFANA_ORG_ID") or "1").strip() or "1"
    from_ms, to_ms = _range_ms(started_at, finished_at)
    # Escape backslash and double-quote for LogQL string literal.
    safe = needle.replace("\\", "\\\\").replace('"', '\\"')
    expr = f'{{job=~".+"}} |= "{safe}"'
    panes = {
        "logs": {
            "datasource": uid,
            "queries": [
                {
                    "refId": "A",
                    "datasource": {"type": "loki", "uid": uid},
                    "expr": expr,
                    "queryType": "range",
                }
            ],
            "range": {"from": str(from_ms), "to": str(to_ms)},
        }
    }
    encoded = quote(json.dumps(panes, separators=(",", ":")))
    return f"{base}/explore?orgId={org}&panes={encoded}&schemaVersion=1"


def prometheus_explore_url(
    *,
    service: str | None = None,
    environment: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    env: str | None = None,
) -> str:
    """Grafana Explore → Prometheus for service/env window (when Grafana connected)."""
    base = _grafana_base(env=env or environment)
    if not base:
        return ""
    try:
        from specs.security.credential_store import resolve_prometheus_base

        if not resolve_prometheus_base(env=env or environment) and not os.getenv(
            "PROMETHEUS_URL"
        ):
            # Still allow Explore via Grafana Prom datasource when only Grafana is set.
            pass
    except Exception:  # noqa: BLE001
        pass
    uid = (os.getenv("GRAFANA_PROM_DATASOURCE_UID") or "prometheus").strip() or "prometheus"
    org = (os.getenv("GRAFANA_ORG_ID") or "1").strip() or "1"
    from_ms, to_ms = _range_ms(started_at, finished_at)
    svc = (service or "").strip() or ".*"
    env_l = (environment or env or "").strip() or ".*"
    expr = (
        f'up{{service=~"{svc}",environment=~"{env_l}"}}'
        if svc != ".*" or env_l != ".*"
        else "up"
    )
    panes = {
        "prom": {
            "datasource": uid,
            "queries": [
                {
                    "refId": "A",
                    "datasource": {"type": "prometheus", "uid": uid},
                    "expr": expr,
                    "range": True,
                }
            ],
            "range": {"from": str(from_ms), "to": str(to_ms)},
        }
    }
    encoded = quote(json.dumps(panes, separators=(",", ":")))
    return f"{base}/explore?orgId={org}&panes={encoded}&schemaVersion=1"


def build_observability_resources(
    *,
    run_id: str | None = None,
    trace_id: str | None = None,
    correlation_id: str | None = None,
    service: str | None = None,
    environment: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    env: str | None = None,
) -> dict[str, Any]:
    """Attach dashboard + Explore links for a run / flow execution."""
    env_n = env or environment
    grafana_ok = bool(_grafana_base(env=env_n))
    prom_connected = False
    try:
        from specs.security.credential_store import (
            resolve_prometheus_base,
            resource_connected,
        )

        prom_connected = bool(resolve_prometheus_base(env=env_n)) or resource_connected(
            "prometheus", env=env_n
        )
        grafana_connected = resource_connected("grafana", env=env_n) or grafana_ok
    except Exception:  # noqa: BLE001
        grafana_connected = grafana_ok

    dash = grafana_run_url(
        service=service,
        environment=environment,
        started_at=started_at,
        finished_at=finished_at,
        run_id=run_id,
        env=env_n,
    )
    embed = grafana_embed_url(
        service=service,
        environment=environment,
        started_at=started_at,
        finished_at=finished_at,
        run_id=run_id,
        env=env_n,
    )
    out: dict[str, Any] = {
        "trace_id": (trace_id or "").strip() or None,
        "correlation_id": (correlation_id or "").strip() or None,
        "grafana_dashboard_url": dash or None,
        "grafana_embed_url": embed or None,
        "grafana_loki_explore_url": grafana_loki_explore_url(
            trace_id,
            correlation_id=correlation_id,
            started_at=started_at,
            finished_at=finished_at,
            env=env_n,
        )
        or None,
        "grafana_tempo_explore_url": grafana_tempo_explore_url(
            trace_id,
            started_at=started_at,
            finished_at=finished_at,
            env=env_n,
        )
        or None,
        "prometheus_explore_url": prometheus_explore_url(
            service=service,
            environment=environment,
            started_at=started_at,
            finished_at=finished_at,
            env=env_n,
        )
        or None,
        "connected": {
            "grafana": bool(grafana_connected),
            "prometheus": bool(prom_connected),
        },
    }
    return out
