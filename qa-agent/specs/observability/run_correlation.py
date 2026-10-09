"""Capture OTEL / correlation ids for Specs, API Flows, and UI runs."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


def capture_run_correlation() -> dict[str, str]:
    """Return trace_id, span_id, correlation_id for the current context."""
    trace_id = ""
    span_id = ""
    try:
        from common.observability.tracing import current_trace_ids

        trace_id, span_id = current_trace_ids()
    except Exception:  # noqa: BLE001
        pass
    correlation_id = f"qa-{uuid.uuid4().hex[:12]}"
    if not trace_id:
        # Stable synthetic id when OTEL is disabled so Loki/Explore still have a needle.
        trace_id = correlation_id.replace("-", "")
    try:
        from common.observability.tracing import set_span_tracking_id

        set_span_tracking_id(correlation_id)
    except Exception:  # noqa: BLE001
        pass
    return {
        "trace_id": trace_id,
        "span_id": span_id or "",
        "correlation_id": correlation_id,
    }


def _iso_from_epoch(value: Any) -> str | None:
    if isinstance(value, (int, float)) and value > 0:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def attach_obs_to_row(row: dict[str, Any] | None) -> dict[str, Any]:
    """Mutate/return a run or execution row with observability_resources."""
    if not isinstance(row, dict):
        return {}
    from specs.observability.grafana_links import build_observability_resources

    run_id = str(row.get("id") or row.get("run_id") or row.get("execution_id") or "")
    env = str(row.get("environment") or row.get("env") or "") or None
    started = _iso_from_epoch(row.get("started_at")) or _iso_from_epoch(
        row.get("created_at")
    )
    finished = _iso_from_epoch(row.get("finished_at")) or _iso_from_epoch(
        row.get("updated_at")
    )
    obs = build_observability_resources(
        run_id=run_id or None,
        trace_id=row.get("trace_id"),
        correlation_id=row.get("correlation_id"),
        service=row.get("service"),
        environment=env,
        started_at=started,
        finished_at=finished,
        env=env,
    )
    row["observability_resources"] = obs
    if obs.get("grafana_dashboard_url") and not row.get("grafana_url"):
        row["grafana_url"] = obs["grafana_dashboard_url"]
    if obs.get("grafana_embed_url") and not row.get("grafana_embed_url"):
        row["grafana_embed_url"] = obs["grafana_embed_url"]
    return row
