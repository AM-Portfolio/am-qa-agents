"""Shared execute path for REST + MCP."""

from __future__ import annotations

import asyncio
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from specs.load import load_ops
from specs.security.acl import Caller, allows_multi_load, enforce_execute_load
from specs.catalog.catalog_loader import (
    apply_preset,
    apply_run_profile,
    apis_for_config,
    default_target_for_service,
    load_service_apis,
    reachable_target_for_service,
)
from specs.config import settings
from specs.load.config_builder import config_from_request, ensure_default_config
from specs.persistence.db.engine import store_mode
from specs.load.load_runner import _planned_api_rows
from specs.payloads.payload_store import apply_payload_refs, apply_payload_set
from specs.persistence.run_store import (
    count_running,
    get_config,
    get_run,
    list_configs,
    save_config,
    save_run,
    update_run,
)
from specs.schemas import RunExecuteRequest


async def execute_run(
    body: RunExecuteRequest,
    *,
    caller: Caller | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    caller = caller or Caller(role="developer")

    if idempotency_key and store_mode() != "json":
        from specs.persistence.stores import db_backend as db

        existing = db.get_idempotency(idempotency_key)
        if existing:
            row = get_run(existing)
            if row:
                return row

    running = count_running()
    if running >= settings.spt_max_concurrent_runs:
        raise HTTPException(
            status_code=429,
            detail=f"Too many concurrent runs ({running}/{settings.spt_max_concurrent_runs})",
        )

    if body.config_id:
        cfg = get_config(body.config_id)
        if not cfg:
            raise HTTPException(status_code=404, detail="Config not found")
    elif body.config:
        cfg = config_from_request(body.config)
    elif body.audience:
        service = body.service or (body.config.service if body.config else None)
        matches = list_configs(service=service, audience=body.audience)
        if not matches:
            raise HTTPException(
                status_code=404,
                detail=f"No profile for audience={body.audience}"
                + (f" service={service}" if service else ""),
            )
        if len(matches) > 1 and not service:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": f"Multiple profiles for audience={body.audience}; pass service or config_id",
                    "config_ids": [m.get("id") for m in matches],
                    "names": [m.get("name") for m in matches],
                },
            )
        if len(matches) > 1:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": f"Multiple profiles for audience={body.audience} service={service}; pass config_id",
                    "config_ids": [m.get("id") for m in matches],
                    "names": [m.get("name") for m in matches],
                },
            )
        cfg = matches[0]
    else:
        cfg = ensure_default_config()

    # Never mutate the stored seed profile in-place; bind request service/env first.
    # Without this, POST {service: am-analysis} kept empty default-smoke → api_count=0.
    cfg = dict(cfg)
    if body.service:
        cfg["service"] = body.service

    audience = str(cfg.get("audience") or "developer").lower()
    enforce_execute_load(
        role=caller.role,
        audience=audience,
        vus=body.vus,
        iterations=body.iterations,
        duration=body.duration,
        preset=body.preset,
    )

    cfg = apply_preset(cfg, body.preset)
    if body.environment:
        cfg["environment"] = body.environment
        cfg["target_url"] = default_target_for_service(
            cfg.get("service") or settings.default_service or "", body.environment
        )
    elif body.service:
        # Service override without env change — refresh target for that service
        cfg["target_url"] = default_target_for_service(
            cfg.get("service") or "",
            cfg.get("environment") or settings.default_environment,
        )
    if body.openapi_version is not None:
        cfg["openapi_version"] = body.openapi_version
    elif body.config and getattr(body.config, "openapi_version", None):
        cfg["openapi_version"] = body.config.openapi_version

    # Playwright / ui-test-agent fields
    if body.test_type:
        cfg["test_type"] = body.test_type
    elif body.config and getattr(body.config, "test_type", None):
        cfg["test_type"] = body.config.test_type
    if body.ui_profile is not None:
        cfg["ui_profile"] = body.ui_profile
    elif body.config and getattr(body.config, "ui_profile", None):
        cfg["ui_profile"] = body.config.ui_profile
    if body.ui_suite is not None:
        cfg["ui_suite"] = body.ui_suite
    elif body.config and getattr(body.config, "ui_suite", None):
        cfg["ui_suite"] = body.config.ui_suite
    if body.ui_profiles is not None:
        cfg["ui_profiles"] = list(body.ui_profiles)
    elif body.config and getattr(body.config, "ui_profiles", None):
        cfg["ui_profiles"] = list(body.config.ui_profiles)
    if body.login_mode is not None:
        cfg["login_mode"] = body.login_mode
    elif body.config and getattr(body.config, "login_mode", None):
        cfg["login_mode"] = body.config.login_mode
    if body.baseline_mode is not None:
        cfg["baseline_mode"] = body.baseline_mode
    elif body.config and getattr(body.config, "baseline_mode", None):
        cfg["baseline_mode"] = body.config.baseline_mode
    if body.design_review_enabled is not None:
        cfg["design_review_enabled"] = body.design_review_enabled
    elif body.config and getattr(body.config, "design_review_enabled", None) is not None:
        cfg["design_review_enabled"] = body.config.design_review_enabled
    if body.report_formats is not None:
        cfg["report_formats"] = list(body.report_formats)
    elif body.config and getattr(body.config, "report_formats", None):
        cfg["report_formats"] = list(body.config.report_formats)
    if getattr(body, "ui_target_url", None):
        cfg["ui_target_url"] = body.ui_target_url
    elif body.config and getattr(body.config, "ui_target_url", None):
        cfg["ui_target_url"] = body.config.ui_target_url
    if body.target_url:
        cfg["target_url"] = body.target_url
    elif body.config and getattr(body.config, "target_url", None):
        cfg["target_url"] = body.config.target_url

    test_type = str(cfg.get("test_type") or "k6").lower()
    # Do not invent a product service name — require request/config/registration.
    if not cfg.get("service"):
        cfg["service"] = settings.default_service or ""

    if test_type in ("playwright", "mixed") and (cfg.get("ui_profile") or cfg.get("ui_suite")):
        from specs.ui_bridge.ui_catalog_store import resolve_ui_run

        cfg = resolve_ui_run(cfg)

    allows_multi = allows_multi_load(caller.role, audience)

    profile = body.profile or (body.config.run_profile if body.config else None) or cfg.get("run_profile")
    if not allows_multi:
        profile = "load"
        payloads = dict(cfg.get("payloads") or {})
        payloads["bench_run"] = {"vus": 1, "iterations": 1}
        cfg["payloads"] = payloads
        body.vus = 1
        body.iterations = 1
        body.duration = None
        body.preset = None
    elif body.preset == "20u-50" or (body.vus and body.vus > 1) or (body.iterations and body.iterations > 1):
        profile = "load"
    cfg = apply_run_profile(cfg, profile)

    set_ver = body.payload_set_version
    if set_ver is None:
        set_ver = cfg.get("payload_set_version")
        if set_ver is None:
            set_ver = ((cfg.get("payloads") or {}).get("payload_set_version"))
    if set_ver is not None:
        cfg = apply_payload_set(cfg, int(set_ver))
    if body.payload_refs:
        cfg = apply_payload_refs(cfg, body.payload_refs)

    selected_api_ids = [str(x) for x in (body.api_ids or []) if x]
    if not selected_api_ids and cfg.get("selected_api_ids"):
        selected_api_ids = [str(x) for x in (cfg.get("selected_api_ids") or []) if x]
    if selected_api_ids and test_type != "playwright":
        cfg["selected_api_ids"] = selected_api_ids
        try:
            apis_for_config(cfg, run_id="validate")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    cfg["target_url"] = reachable_target_for_service(
        cfg.get("service") or settings.default_service or "",
        cfg.get("environment") or settings.default_environment,
        cfg.get("target_url"),
    )

    if allows_multi and (body.vus is not None or body.iterations is not None or body.duration is not None):
        payloads = dict(cfg.get("payloads") or {})
        bench = dict(payloads.get("bench_run") or {})
        if body.vus is not None:
            bench["vus"] = body.vus
        if body.iterations is not None:
            bench["iterations"] = body.iterations
            bench.pop("duration", None)
        elif body.duration is not None:
            bench["duration"] = body.duration
            bench.pop("iterations", None)
        if (body.vus and body.vus > 1) or (body.iterations and body.iterations > 1):
            profile = "load"
            cfg["run_profile"] = "load"
        payloads["bench_run"] = bench
        cfg["payloads"] = payloads
        if profile != "debug":
            cfg["run_profile"] = "load"
    elif not allows_multi:
        payloads = dict(cfg.get("payloads") or {})
        payloads["bench_run"] = {"vus": 1, "iterations": 1}
        cfg["payloads"] = payloads
        cfg["run_profile"] = "load"

    if body.save_config and body.config:
        cfg = save_config(config_from_request(body.config))

    audit = {
        "audience": audience,
        "caller_role": caller.role,
        "caller_key_id": caller.key_id,
    }

    if body.wait is True:
        record = await load_ops.run_test_from_config(cfg, triggered_by=body.triggered_by)
        record.update(audit)
        save_run(record)
        if idempotency_key and store_mode() != "json":
            from specs.persistence.stores import db_backend as db

            db.put_idempotency(idempotency_key, str(record.get("id")))
        return record

    run_id = str(uuid.uuid4())
    bench = ((cfg.get("payloads") or {}).get("bench_run")) or {}
    auth = ((cfg.get("payloads") or {}).get("auth_env")) or {}
    started_at = datetime.now(timezone.utc).isoformat()
    planned_rows: list[dict[str, Any]] = []
    apis_tested: list[dict[str, Any]] = []
    if test_type != "playwright":
        try:
            _, planned = apis_for_config(cfg, run_id=run_id)
            planned_rows = _planned_api_rows(planned)
            apis_tested = [
                {
                    "id": a.get("id"),
                    "name": a.get("name"),
                    "method": a.get("method"),
                    "path": a.get("path"),
                }
                for a in planned
            ]
            if not cfg.get("openapi_version"):
                cat = load_service_apis(
                    cfg.get("service") or settings.default_service or "",
                    cfg.get("environment") or settings.default_environment,
                )
                if cat.get("openapi_version"):
                    cfg["openapi_version"] = cat.get("openapi_version")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception:
            try:
                raw = (load_service_apis(cfg.get("service") or settings.default_service or "").get("apis") or [])
                planned_rows = _planned_api_rows(raw)
                apis_tested = [
                    {"id": a.get("id"), "name": a.get("name"), "method": a.get("method"), "path": a.get("path")}
                    for a in raw
                    if a.get("id")
                ]
            except Exception:
                planned_rows = []
                apis_tested = []
    else:
        label = cfg.get("ui_suite") or cfg.get("ui_profile") or settings.ui_test_default_profile
        planned_rows = [
            {
                "api_id": str(label),
                "name": str(label),
                "method": "UI",
                "path": "/",
                "trace_available": False,
                "checks_passed": None,
                "request_count": None,
                "pass_count": None,
                "fail_count": None,
                "status": "running",
                "kind": "ui_step",
            }
        ]
    placeholder = {
        "id": run_id,
        "started_at": started_at,
        "status": "running",
        "passed": False,
        "runner": "ui-test-agent" if test_type == "playwright" else "k6-local",
        "run_profile": cfg.get("run_profile") or "load",
        "config_id": cfg.get("id"),
        "config_name": cfg.get("name", "unnamed"),
        "service": cfg.get("service") or settings.default_service or "",
        "environment": cfg.get("environment", settings.default_environment),
        "openapi_version": cfg.get("openapi_version"),
        "test_type": cfg.get("test_type", "k6"),
        "ui_profile": cfg.get("ui_profile"),
        "ui_suite": cfg.get("ui_suite"),
        "triggered_by": body.triggered_by,
        "target_url": cfg.get("target_url") or settings.poc_target_url,
        "api_count": len(planned_rows) or None,
        "api_ids": selected_api_ids or None,
        "vus": bench.get("vus") if test_type != "playwright" else None,
        "iterations": bench.get("iterations") if test_type != "playwright" else None,
        "duration": bench.get("duration") if test_type != "playwright" else None,
        "auth_username": auth.get("username"),
        "payloads_used": {
            "bench_run": dict(bench) if test_type != "playwright" else {},
            "auth_env": {k: auth[k] for k in ("username", "user_id", "identity_url") if auth.get(k)},
            "run_params": {
                "profile": cfg.get("run_profile") or "load",
                "vus": bench.get("vus"),
                "duration": bench.get("duration"),
                "iterations": bench.get("iterations"),
                "triggered_by": body.triggered_by,
                "api_ids": selected_api_ids or None,
                "openapi_version": cfg.get("openapi_version"),
                "ui_profile": cfg.get("ui_profile"),
                "ui_suite": cfg.get("ui_suite"),
            },
            "apis_tested": apis_tested,
        },
        "steps": [{"step": "queued", "status": "running"}],
        "metrics_summary": {},
        "api_summary": planned_rows,
        "live": {
            "phase": "queued",
            "message": (
                "Run accepted — starting Playwright…"
                if test_type == "playwright"
                else "Run accepted — starting…"
            ),
            "vus": bench.get("vus"),
            "iterations": bench.get("iterations"),
            "duration": bench.get("duration"),
            "api_count": len(planned_rows),
            "completed_iterations": 0,
            "total_iterations": bench.get("iterations"),
            "api_hits": 0,
            "pct": 0,
            "by_api": {},
        },
        "error": None,
        **audit,
    }
    save_run(placeholder)
    if idempotency_key and store_mode() != "json":
        from specs.persistence.stores import db_backend as db

        db.put_idempotency(idempotency_key, run_id)

    triggered_by = body.triggered_by

    def _bg_thread() -> None:
        def on_progress(live: dict) -> None:
            current = get_run(run_id) or {}
            # Stop/cancel must win — never flip terminal status back to running
            cur_status = str(current.get("status") or "").lower()
            if cur_status in {"cancelled", "failed", "passed", "completed", "error"}:
                return
            prev = dict(current.get("live") or {})
            live_copy = dict(live)
            api_summary = live_copy.pop("api_summary", None)
            merged = {**prev, **{k: v for k, v in live_copy.items() if v is not None}}
            for key in ("completed_iterations", "api_hits", "pct", "elapsed_s"):
                try:
                    merged[key] = max(int(prev.get(key) or 0), int(merged.get(key) or 0))
                except (TypeError, ValueError):
                    pass
            if prev.get("by_api") and not merged.get("by_api"):
                merged["by_api"] = prev["by_api"]
            patch: dict = {"status": "running", "live": merged}
            cur_summary = current.get("api_summary") or []
            if api_summary is not None and not cur_summary:
                patch["api_summary"] = api_summary
            update_run(run_id, patch)

        async def _run() -> None:
            try:
                record = await load_ops.run_test_from_config(
                    cfg,
                    triggered_by=triggered_by,
                    run_id=run_id,
                    progress=on_progress,
                )
                record["started_at"] = started_at
                record.update(audit)
                current = get_run(run_id) or {}
                if current.get("status") == "cancelled" and record.get("status") != "cancelled":
                    record["status"] = "cancelled"
                    record["passed"] = False
                    record["error"] = current.get("error") or "stopped by user"
                save_run(record)
            except Exception as exc:
                current = get_run(run_id) or {}
                if current.get("status") == "cancelled":
                    return
                update_run(
                    run_id,
                    {
                        "status": "failed",
                        "passed": False,
                        "finished_at": datetime.now(timezone.utc).isoformat(),
                        "error": str(exc),
                        "live": {"phase": "error", "message": str(exc)},
                    },
                )

        asyncio.run(_run())

    threading.Thread(target=_bg_thread, name=f"spt-run-{run_id[:8]}", daemon=True).start()
    return placeholder


def execute_run_sync(
    *,
    config_id: str | None = None,
    audience: str | None = None,
    service: str | None = None,
    vus: int | None = None,
    iterations: int | None = None,
    duration: str | None = None,
    profile: str | None = None,
    triggered_by: str = "mcp",
    wait: bool = False,
    caller: Caller | None = None,
) -> dict[str, Any]:
    body = RunExecuteRequest(
        config_id=config_id,
        audience=audience,
        service=service,
        vus=vus,
        iterations=iterations,
        duration=duration,
        profile=profile,
        triggered_by=triggered_by,
        wait=wait,
    )
    return asyncio.run(execute_run(body, caller=caller or Caller(role="agent")))
