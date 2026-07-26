from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from specs.security.acl import AclMiddleware, Caller, seed_bootstrap_keys
from specs.api.platform import router as platform_router
from specs.config import settings
from specs.load.config_builder import config_from_request, ensure_default_config
from specs.portal.dashboard import render_portal
from specs.persistence.db.engine import init_db, store_mode
from specs.observability.grafana_links import grafana_embed_url, grafana_run_url
from specs.load import load_ops
from specs.load.load_runner import (
    get_run_api_index,
    get_run_trace,
    get_run_trace_at,
    list_run_traces,
)
from specs.mcp.control import mount_mcp
from specs.payloads.payload_store import (
    create_payload_set,
    delete_payload,
    ensure_payload_set,
    get_payload,
    get_payload_set,
    list_payload_sets,
    list_payloads,
    save_from_trace,
    save_payload,
    set_active_payload_set,
    upsert_api_in_payload_set,
)
from specs.portal.portal_paths import (
    flutter_portal_available,
    portal_flutter_web_dir,
    portal_static_dir,
)
from specs.load.runners import process_registry
from specs.persistence.run_store import (
    delete_config,
    get_config,
    get_run,
    increment_run_progress,
    list_configs,
    list_runs,
    save_config,
    save_run,
    slim_run_for_list,
    update_run,
)
from specs.schemas import (
    PayloadCreateRequest,
    PayloadSetCreateRequest,
    PayloadSetUpsertApiRequest,
    RunExecuteRequest,
    SavePayloadRequest,
    TestConfigIn,
    TestConfigUpdate,
    UiFlowIn,
    UiFlowUpdate,
    UiSuiteIn,
    UiSuiteUpdate,
)
from specs.services import compare_runs, previous_for_profile
from specs.services import execute_svc
from specs.persistence.trace_store import filter_api_index

app = FastAPI(
    title="AM Test Agent",
    version="1.0.0",
    description="Unified test agent — API load (k6), UI (Playwright), mixed suites, OpenAPI, Grafana, MCP control",
    root_path=settings.root_path.rstrip("/") if settings.root_path else "",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

_STATIC_DIR = portal_static_dir()
if _STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
app.include_router(platform_router)
# Flutter web on another origin (e.g. localhost:8151 → :8150) needs CORS.
# Cluster traffic is same-origin via Traefik; local allow-list is for portal dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8151",
        "http://127.0.0.1:8151",
        "http://localhost:8150",
        "http://127.0.0.1:8150",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AclMiddleware)
mount_mcp(app)


class _FlutterNoCacheMiddleware:
    """Avoid CDN/browser serving stale Flutter SPA shells after deploys."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        # Traefik may forward /spt-poc/ui/... (full path) or /ui/... (stripped).
        no_cache = "/ui" in path and (
            path.endswith(".js")
            or path.endswith(".html")
            or path.rstrip("/").endswith("/ui")
            or path.endswith("/")
        )

        async def send_wrapper(message: Any) -> None:
            if no_cache and message["type"] == "http.response.start":
                headers = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() not in (b"cache-control", b"expires", b"pragma")
                ]
                headers.append((b"cache-control", b"no-cache, no-store, must-revalidate"))
                headers.append((b"pragma", b"no-cache"))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper if no_cache else send)


_FLUTTER_DIR = portal_flutter_web_dir() if settings.spt_portal_flutter else None
if _FLUTTER_DIR is not None:
    app.add_middleware(_FlutterNoCacheMiddleware)
    app.mount(
        "/ui",
        StaticFiles(directory=str(_FLUTTER_DIR), html=True),
        name="flutter_ui",
    )


@app.on_event("startup")
async def startup() -> None:
    if store_mode() != "json":
        init_db()
        try:
            from specs.persistence.db.migrate_json import migrate_all

            migrate_all()
        except Exception:
            pass
        seed_bootstrap_keys()
        # Orphaned "running" rows from crashed processes / JSON migration
        try:
            from specs.persistence.run_store import list_runs, update_run

            rows, _ = list_runs(limit=200, status="running")
            for row in rows:
                update_run(
                    str(row["id"]),
                    {
                        "status": "failed",
                        "passed": False,
                        "error": row.get("error") or "stale running state cleared on startup",
                        "finished_at": datetime.now(timezone.utc).isoformat(),
                        "live": {"phase": "error", "message": "cleared on startup"},
                    },
                )
        except Exception:
            pass
    ensure_default_config()


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    prefix = settings.root_path.rstrip("/") if settings.root_path else ""
    return RedirectResponse(url=f"{prefix}/ui")


@app.get("/ui", include_in_schema=False)
async def dashboard_ui():
    # Flutter StaticFiles is mounted at /ui when enabled + build present.
    if settings.spt_portal_flutter and flutter_portal_available():
        prefix = settings.root_path.rstrip("/") if settings.root_path else ""
        return RedirectResponse(url=f"{prefix}/ui/")
    return HTMLResponse(render_portal())


@app.get("/api/portal/mode", include_in_schema=False)
async def portal_mode() -> dict[str, Any]:
    return {
        "flutter_enabled": bool(settings.spt_portal_flutter),
        "flutter_available": flutter_portal_available(),
        "flutter_dir": str(portal_flutter_web_dir() or ""),
    }


@app.get("/api/runs")
async def api_list_runs(
    service: str | None = None,
    environment: str | None = None,
    status: str | None = None,
    config_name: str | None = None,
    config_id: str | None = None,
    run_id: str | None = None,
    test_type: str | None = None,
    triggered_by: str | None = None,
    q: str | None = None,
    started_from: str | None = Query(None, alias="from"),
    started_to: str | None = Query(None, alias="to"),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    runs, total = list_runs(
        limit=limit,
        offset=offset,
        service=service,
        environment=environment,
        status=status,
        config_name=config_name,
        config_id=config_id,
        run_id=run_id,
        test_type=test_type,
        triggered_by=triggered_by,
        q=q,
        started_from=started_from,
        started_to=started_to,
    )
    return {
        "runs": [slim_run_for_list(r) for r in runs],
        "count": len(runs),
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/runs/compare")
async def api_compare_runs(
    a: str = Query(..., description="Baseline run id"),
    b: str = Query(..., description="Compare run id"),
) -> dict:
    result = compare_runs(a, b)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result)
    return result


@app.get("/api/runs/{run_id}")
async def api_get_run(run_id: str) -> dict:
    row = get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    # Always rebuild so UID/vars track current GRAFANA_* settings (old runs
    # may still point at legacy k6-load-testing).
    row["grafana_url"] = grafana_run_url(
        service=row.get("service"),
        environment=row.get("environment"),
        started_at=row.get("started_at"),
        finished_at=row.get("finished_at"),
        run_id=run_id,
    )
    row["grafana_embed_url"] = grafana_embed_url(
        service=row.get("service"),
        environment=row.get("environment"),
        started_at=row.get("started_at"),
        finished_at=row.get("finished_at"),
        run_id=run_id,
    )
    if row.get("api_pass_count") is None or row.get("api_fail_count") is None:
        counts = api_outcome_counts(row.get("api_summary"))
        row.setdefault("api_pass_count", counts["api_pass_count"])
        row.setdefault("api_fail_count", counts["api_fail_count"])
        if not row.get("api_count"):
            row["api_count"] = counts["api_count"]
    return row


@app.post("/api/runs/{run_id}/progress")
async def api_run_progress(run_id: str, body: dict[str, Any] = Body(default_factory=dict)) -> dict:
    """Lightweight callback from k6 for live UI progress (file-backed, reload-safe)."""
    body = body or {}
    result = increment_run_progress(
        run_id,
        event=str(body.get("event") or "tick"),
        total=body.get("total"),
        api_count=body.get("api_count"),
        vu=body.get("vu"),
        api_id=body.get("api_id"),
    )
    if not result:
        return {"ok": False, "reason": "missing"}
    return result


_sample_locks: dict[str, asyncio.Lock] = {}


def _sample_lock(run_id: str) -> asyncio.Lock:
    lock = _sample_locks.get(run_id)
    if lock is None:
        lock = asyncio.Lock()
        _sample_locks[run_id] = lock
    return lock


@app.post("/api/runs/{run_id}/sample")
async def api_run_sample(run_id: str, body: dict[str, Any] = Body(default_factory=dict)) -> dict:
    """Receive one request/response sample from a k6 VU (per-call traces for inspector)."""
    row = get_run(run_id)
    if not row:
        return {"ok": False, "reason": "missing"}
    if not body.get("api_id"):
        return {"ok": False, "reason": "no_api_id"}
    art_dir = Path(settings.data_dir) / "artifacts" / run_id
    art_dir.mkdir(parents=True, exist_ok=True)
    path = art_dir / "traces.json"
    async with _sample_lock(run_id):
        traces: list[dict[str, Any]] = []
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    traces = data
            except Exception:
                traces = []
        if len(traces) >= settings.trace_max_calls:
            return {"ok": True, "api_id": str(body.get("api_id")), "count": len(traces), "truncated": True}
        aid = str(body.get("api_id"))
        sample = dict(body)
        # Server assigns monotonic call_index (k6 VUs have separate JS heaps)
        sample["call_index"] = len(traces) + 1
        traces.append(sample)
        path.write_text(json.dumps(traces, indent=2, default=str), encoding="utf-8")
        # Reflect latest HTTP status into live api_summary when present
        api_summary = list(row.get("api_summary") or [])
        for api_row in api_summary:
            if str(api_row.get("api_id")) == aid:
                api_row["status"] = (sample.get("response") or {}).get("status")
                api_row["trace_available"] = True
                if sample.get("timings"):
                    api_row["duration_ms"] = (sample.get("timings") or {}).get("duration_ms")
                break
        if api_summary:
            update_run(run_id, {"api_summary": api_summary})
        return {"ok": True, "api_id": aid, "count": len(traces)}


@app.get("/api/runs/{run_id}/apis")
async def api_run_apis(
    run_id: str,
    failed_only: bool = False,
    q: str | None = None,
    limit: int = Query(500, le=1000),
    offset: int = 0,
) -> dict:
    row = get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    apis = get_run_api_index(run_id) or row.get("api_summary") or []
    filtered, total = filter_api_index(apis, failed_only=failed_only, q=q, limit=limit, offset=offset)
    return {"run_id": run_id, "apis": filtered, "count": len(filtered), "total": total}


@app.get("/api/runs/{run_id}/traces")
async def api_run_traces(
    run_id: str,
    failed_only: bool = False,
    api_id: str | None = None,
    limit: int = Query(500, le=1000),
    offset: int = 0,
) -> dict:
    row = get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    traces, total = list_run_traces(
        run_id, api_id=api_id, failed_only=failed_only, limit=limit, offset=offset
    )
    return {"run_id": run_id, "traces": traces, "count": len(traces), "total": total}


@app.get("/api/runs/{run_id}/traces/{index}")
async def api_run_trace_at_index(run_id: str, index: int) -> dict:
    row = get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    trace = get_run_trace_at(run_id, index, redact=True)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return {"run_id": run_id, "index": index, "trace": trace}


@app.get("/api/runs/{run_id}/apis/{api_id}/trace")
async def api_run_api_trace(run_id: str, api_id: str) -> dict:
    row = get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    trace = get_run_trace(run_id, api_id, redact=True)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found for this API")
    return {"run_id": run_id, "api_id": api_id, "trace": trace}


@app.post("/api/runs/{run_id}/apis/{api_id}/save-payload")
async def api_save_payload_from_run(run_id: str, api_id: str, body: SavePayloadRequest | None = None) -> dict:
    row = get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    name = (body.name if body else None) or "default"
    service = (body.service if body else None) or row.get("service")
    try:
        saved = save_from_trace(run_id, api_id, name=name, service=service)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return saved


@app.get("/api/payloads")
async def api_list_payloads(
    service: str | None = None,
    api_id: str | None = None,
) -> dict:
    rows = list_payloads(service=service, api_id=api_id)
    return {"payloads": rows, "count": len(rows)}


@app.get("/api/payloads/{service}/{api_id}")
async def api_list_payloads_for_api(service: str, api_id: str) -> dict:
    rows = list_payloads(service=service, api_id=api_id)
    return {"service": service, "api_id": api_id, "payloads": rows, "count": len(rows)}


@app.get("/api/payloads/{service}/{api_id}/{name}")
async def api_get_payload(
    service: str,
    api_id: str,
    name: str,
    version: int | None = None,
) -> dict:
    row = get_payload(service, api_id, name, version)
    if not row:
        raise HTTPException(status_code=404, detail="Payload not found")
    return row


@app.post("/api/payloads")
async def api_create_payload(body: PayloadCreateRequest) -> dict:
    saved = save_payload(
        {
            "service": body.service,
            "api_id": body.api_id,
            "name": body.name,
            "request": body.request,
            "response": body.response,
            "meta": body.meta,
            "source_run_id": body.source_run_id,
        },
        bump=body.bump,
    )
    payload_set = None
    if body.into_set:
        payload_set = upsert_api_in_payload_set(
            body.service,
            body.api_id,
            version=body.set_version,
            request=body.request,
            response=body.response,
            meta=body.meta,
            name=body.name,
            bump_set=body.bump_set,
        )
    return {"payload": saved, "payload_set": payload_set}


@app.get("/api/payload-sets")
async def api_list_payload_sets(service: str = Query(...)) -> dict:
    return list_payload_sets(service)


@app.get("/api/payload-sets/{service}")
async def api_list_payload_sets_path(service: str) -> dict:
    return list_payload_sets(service)


@app.get("/api/payload-sets/{service}/{version}")
async def api_get_payload_set(service: str, version: int) -> dict:
    row = get_payload_set(service, version)
    if not row:
        raise HTTPException(status_code=404, detail="Payload set not found")
    return row


@app.post("/api/payload-sets")
async def api_create_payload_set(body: PayloadSetCreateRequest) -> dict:
    return create_payload_set(
        body.service,
        label=body.label,
        clone_from=body.clone_from,
        make_active=body.make_active,
    )


@app.post("/api/payload-sets/{service}/ensure")
async def api_ensure_payload_set(service: str, label: str = "working") -> dict:
    return ensure_payload_set(service, label=label)


@app.post("/api/payload-sets/{service}/{version}/activate")
async def api_activate_payload_set(service: str, version: int) -> dict:
    try:
        return set_active_payload_set(service, version)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/api/payload-sets/{service}/apis/{api_id}")
async def api_upsert_payload_set_api(
    service: str,
    api_id: str,
    body: PayloadSetUpsertApiRequest,
) -> dict:
    try:
        return upsert_api_in_payload_set(
            service,
            api_id,
            version=body.version,
            request=body.request,
            response=body.response,
            meta=body.meta,
            name=body.name,
            bump_set=body.bump_set,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/payloads/{service}/{api_id}/{name}/{version}")
async def api_delete_payload(service: str, api_id: str, name: str, version: int) -> dict:
    if not delete_payload(service, api_id, name, version):
        raise HTTPException(status_code=404, detail="Payload not found")
    return {"deleted": True, "service": service, "api_id": api_id, "name": name, "version": version}


@app.post("/api/runs/execute")
async def api_execute_run(body: RunExecuteRequest, request: Request) -> dict:
    caller = getattr(request.state, "spt_caller", None) or Caller(role="developer")
    idem = (request.headers.get("idempotency-key") or "").strip() or None
    return await execute_svc.execute_run(body, caller=caller, idempotency_key=idem)


@app.get("/api/runs/{run_id}/baseline")
async def api_run_baseline(run_id: str) -> dict:
    row = get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    prev = previous_for_profile(str(row.get("config_id") or ""), exclude_run_id=run_id)
    if not prev:
        return {"ok": False, "message": "no previous run for profile"}
    cmp = compare_runs(str(prev.get("id")), run_id)
    return {"ok": True, "previous": prev, "compare": cmp}


@app.post("/api/runs/{run_id}/stop")
async def api_stop_run(run_id: str) -> dict:
    row = get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    if row.get("status") != "running":
        return {"ok": True, "status": row.get("status"), "message": "already finished"}
    stop_result = process_registry.request_stop(run_id)
    update_run(
        run_id,
        {
            "status": "cancelled",
            "passed": False,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error": "stopped by user",
            "live": {"phase": "cancelled", "message": "Stopped by user"},
        },
    )
    return {"ok": True, "status": "cancelled", "stop": stop_result}


def _list_profiles_payload(
    service: str | None = None,
    environment: str | None = None,
    audience: str | None = None,
) -> dict:
    configs = list_configs(service=service, environment=environment, audience=audience)
    if not configs:
        configs = [ensure_default_config()]
        configs = list_configs(service=service, environment=environment, audience=audience) or configs
    return {"configs": configs, "profiles": configs, "count": len(configs)}


@app.get("/api/configs")
async def api_list_configs(
    service: str | None = None,
    environment: str | None = None,
    audience: str | None = None,
) -> dict:
    return _list_profiles_payload(service, environment, audience)


@app.get("/api/profiles")
async def api_list_profiles(
    service: str | None = None,
    environment: str | None = None,
    audience: str | None = None,
) -> dict:
    return _list_profiles_payload(service, environment, audience)


@app.get("/api/profiles/default")
async def api_default_profile() -> dict:
    return ensure_default_config()


@app.get("/api/profiles/{config_id}")
async def api_get_profile(config_id: str) -> dict:
    row = get_config(config_id)
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")
    return row


@app.post("/api/profiles")
async def api_create_profile(body: TestConfigIn) -> dict:
    return save_config(config_from_request(body))


@app.put("/api/profiles/{config_id}")
async def api_update_profile(config_id: str, body: TestConfigUpdate) -> dict:
    return await api_update_config(config_id, body)


@app.delete("/api/profiles/{config_id}")
async def api_delete_profile(config_id: str) -> dict:
    if not delete_config(config_id):
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"deleted": config_id}


@app.get("/api/configs/default")
async def api_default_config() -> dict:
    return ensure_default_config()


@app.get("/api/configs/{config_id}")
async def api_get_config(config_id: str) -> dict:
    row = get_config(config_id)
    if not row:
        raise HTTPException(status_code=404, detail="Config not found")
    return row


@app.post("/api/configs")
async def api_create_config(body: TestConfigIn) -> dict:
    return save_config(config_from_request(body))


@app.put("/api/configs/{config_id}")
async def api_update_config(config_id: str, body: TestConfigUpdate) -> dict:
    existing = get_config(config_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Config not found")
    patch = body.model_dump(exclude_unset=True)
    payloads_patch = None
    if body.payloads is not None:
        payloads_patch = body.payloads.model_dump(exclude_unset=True)
        patch.pop("payloads", None)
    scripts_patch = patch.pop("scripts", None)
    merged = {**existing, **patch}
    if payloads_patch is not None:
        existing_payloads = dict(existing.get("payloads") or {})
        # Nested merge for auth_env / bench_run so partial updates do not wipe keys
        if isinstance(payloads_patch.get("auth_env"), dict):
            payloads_patch["auth_env"] = {
                **(existing_payloads.get("auth_env") or {}),
                **payloads_patch["auth_env"],
            }
        if isinstance(payloads_patch.get("bench_run"), dict):
            payloads_patch["bench_run"] = {
                **(existing_payloads.get("bench_run") or {}),
                **payloads_patch["bench_run"],
            }
        merged["payloads"] = {**existing_payloads, **payloads_patch}
        if "payload_set_version" in payloads_patch and payloads_patch["payload_set_version"] is not None:
            merged["payload_set_version"] = payloads_patch["payload_set_version"]
    if "payload_set_version" in patch:
        merged["payload_set_version"] = patch["payload_set_version"]
        payloads = dict(merged.get("payloads") or {})
        payloads["payload_set_version"] = patch["payload_set_version"]
        merged["payloads"] = payloads
    if scripts_patch is not None:
        merged["scripts"] = {**existing.get("scripts", {}), **scripts_patch}
    merged["id"] = config_id
    return save_config(merged)


@app.delete("/api/configs/{config_id}")
async def api_delete_config(config_id: str) -> dict:
    if not delete_config(config_id):
        raise HTTPException(status_code=404, detail="Config not found")
    return {"deleted": config_id}


@app.post("/api/runs/{run_id}/save-config")
async def api_save_config_from_run(run_id: str, name: str | None = None) -> dict:
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    snap = run.get("config_snapshot") or {}
    payloads = run.get("payloads_used") or snap.get("payloads") or {}
    cfg = save_config(
        {
            "name": name or f"from-run-{run_id[:8]}",
            "description": f"Saved from run {run_id}",
            "environment": run.get("environment") or settings.default_environment,
            "service": run.get("service") or settings.default_service or "",
            "test_type": run.get("test_type") or "k6",
            "run_profile": run.get("run_profile") or snap.get("run_profile") or "load",
            "audience": snap.get("audience") or "developer",
            "payload_set_version": snap.get("payload_set_version")
            or (payloads.get("payload_set_version") if isinstance(payloads, dict) else None),
            "openapi_version": run.get("openapi_version"),
            "target_url": run.get("target_url"),
            "payloads": payloads,
            "scripts": snap.get("scripts") or {},
        }
    )
    return cfg

@app.get("/api/runs/{run_id}/export")
async def api_export_run(run_id: str) -> dict:
    row = get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    return row


@app.get("/api/ui-test/profiles")
async def api_ui_test_profiles() -> dict:
    """List ui-test-agent flows/suites with friendly labels + agent online status."""
    from specs.config import settings
    from specs.ui_bridge.ui_catalog_store import merge_catalog
    from specs.ui_bridge.ui_flow_catalog import build_ui_flow_catalog
    from specs.ui_bridge.ui_test_client import UiTestAgentError, list_profiles

    agent_url = (settings.ui_test_agent_url or "").rstrip("/") or None
    try:
        raw = await list_profiles()
        base = build_ui_flow_catalog(
            deterministic=list(raw.get("deterministic") or []),
            release_gate=list(raw.get("release_gate") or []),
            suites=list(raw.get("suites") or []),
            agent_online=True,
            agent_url=agent_url,
        )
    except UiTestAgentError as exc:
        base = build_ui_flow_catalog(
            agent_online=False,
            agent_url=agent_url,
            error=str(exc),
        )
    except Exception as exc:
        base = build_ui_flow_catalog(
            agent_online=False,
            agent_url=agent_url,
            error=f"ui-test-agent unreachable: {exc}",
        )
    return merge_catalog(base)


@app.post("/api/ui-test/flows")
async def api_ui_create_flow(body: UiFlowIn) -> dict:
    from specs.ui_bridge.ui_catalog_store import UiCatalogError, upsert_flow

    try:
        return upsert_flow(body.model_dump(), create=True)
    except UiCatalogError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/ui-test/flows/{flow_id}")
async def api_ui_update_flow(flow_id: str, body: UiFlowUpdate) -> dict:
    from specs.ui_bridge.ui_catalog_store import UiCatalogError, upsert_flow

    patch = body.model_dump(exclude_unset=True)
    patch["id"] = flow_id
    try:
        return upsert_flow(patch, create=False)
    except UiCatalogError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/ui-test/flows/{flow_id}")
async def api_ui_delete_flow(flow_id: str, reset: bool = False) -> dict:
    from specs.ui_bridge.ui_catalog_store import UiCatalogError, delete_flow

    try:
        return delete_flow(flow_id, reset=reset)
    except UiCatalogError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/ui-test/suites")
async def api_ui_create_suite(body: UiSuiteIn) -> dict:
    from specs.ui_bridge.ui_catalog_store import UiCatalogError, upsert_suite

    try:
        return upsert_suite(body.model_dump(), create=True)
    except UiCatalogError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/ui-test/suites/{suite_id}")
async def api_ui_update_suite(suite_id: str, body: UiSuiteUpdate) -> dict:
    from specs.ui_bridge.ui_catalog_store import UiCatalogError, upsert_suite

    patch = body.model_dump(exclude_unset=True)
    patch["id"] = suite_id
    try:
        return upsert_suite(patch, create=False)
    except UiCatalogError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/ui-test/suites/{suite_id}")
async def api_ui_delete_suite(suite_id: str, reset: bool = False) -> dict:
    from specs.ui_bridge.ui_catalog_store import UiCatalogError, delete_suite

    try:
        return delete_suite(suite_id, reset=reset)
    except UiCatalogError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/runs/{run_id}/ui-report")
async def api_run_ui_report(run_id: str) -> dict:
    row = get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    if row.get("ui_report"):
        return {"run_id": run_id, "ui_report": row["ui_report"]}
    path = Path(settings.data_dir) / "artifacts" / run_id / "ui-report.json"
    if path.is_file():
        return {"run_id": run_id, "ui_report": json.loads(path.read_text(encoding="utf-8"))}
    raise HTTPException(status_code=404, detail="UI report not found for this run")


@app.get("/api/runs/{run_id}/artifacts")
async def api_run_artifacts(run_id: str) -> dict:
    """List downloadable attachments for a run (HTML report, traces, etc.)."""
    row = get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    from specs.persistence.artifact_store import artifact_dir, portal_artifact_url

    art_dir = artifact_dir(run_id)
    known = {str(a.get("name")): a for a in (row.get("artifacts") or []) if a.get("name")}
    on_disk: dict[str, Path] = {}
    if art_dir.is_dir():
        for path in art_dir.iterdir():
            if path.is_file():
                on_disk[path.name] = path

    names = set(on_disk) | set(known)
    # Virtual durable report when DB has ui_report but disk/MinIO lost the HTML
    if row.get("ui_report") and "ui-report.html" not in names:
        names.add("ui-report.html")
    if row.get("ui_report") and "ui-report.json" not in names:
        names.add("ui-report.json")

    files: list[dict[str, Any]] = []
    for name in sorted(names):
        meta = known.get(name) or {}
        path = on_disk.get(name)
        size = path.stat().st_size if path is not None else meta.get("size")
        available = path is not None or bool(meta.get("minio_key")) or (
            name in ("ui-report.html", "ui-report.json") and bool(row.get("ui_report"))
        )
        files.append(
            {
                "name": name,
                "size": size,
                "url": portal_artifact_url(run_id, name),
                "minio_url": meta.get("minio_url"),
                "kind": _artifact_kind(name),
                "available": available,
            }
        )
    return {"run_id": run_id, "artifacts": files, "count": len(files)}


def _artifact_kind(name: str) -> str:
    n = name.lower()
    if n.endswith(".html"):
        return "report"
    if n.endswith(".pdf"):
        return "pdf"
    if n.endswith(".zip"):
        return "trace"
    if n.endswith(".json"):
        return "json"
    if n.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return "image"
    return "file"


def _artifact_media(name: str) -> str:
    if name.endswith(".html"):
        return "text/html"
    if name.endswith(".json"):
        return "application/json"
    if name.endswith(".pdf"):
        return "application/pdf"
    if name.endswith(".zip"):
        return "application/zip"
    if name.endswith(".png"):
        return "image/png"
    return "application/octet-stream"


@app.get("/api/runs/{run_id}/artifacts/{name}")
async def api_run_artifact_file(run_id: str, name: str):
    from fastapi.responses import FileResponse, Response

    from specs.persistence.artifact_store import download_from_minio
    from specs.persistence.ui_report_html import render_ui_report_html

    row = get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    # Prevent path traversal
    safe = Path(name).name
    if safe != name or ".." in name or "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="Invalid artifact name")
    path = Path(settings.data_dir) / "artifacts" / run_id / safe
    media = _artifact_media(safe)
    if path.is_file():
        return FileResponse(path, media_type=media, filename=safe)

    # MinIO fallback (when credentials + key were recorded at persist time)
    known = {str(a.get("name")): a for a in (row.get("artifacts") or []) if a.get("name")}
    meta = known.get(safe) or {}
    minio_key = meta.get("minio_key")
    if minio_key:
        blob = await download_from_minio(str(minio_key))
        if blob:
            return Response(content=blob, media_type=media, headers={
                "Content-Disposition": f'inline; filename="{safe}"',
            })

    # Durable JSON / HTML from run metadata (survives ephemeral DATA_DIR)
    if safe == "ui-report.json" and row.get("ui_report"):
        body = json.dumps(row["ui_report"], indent=2, default=str).encode("utf-8")
        return Response(content=body, media_type="application/json")
    if safe == "ui-report.html" and row.get("ui_report"):
        traces: list[dict[str, Any]] = []
        try:
            rows, _total = list_run_traces(run_id, limit=200)
            traces = list(rows or [])
        except Exception:
            traces = []
        if not traces and isinstance(row.get("api_summary"), list):
            # Disk wiped — fall back to api_summary rows stored in Postgres
            traces = [
                {
                    "kind": "ui_step" if str(a.get("method") or "").upper() in ("STEP", "FLOW", "UI") else "http",
                    "call_index": i + 1,
                    "api_id": a.get("api_id") or a.get("id"),
                    "name": a.get("name") or a.get("api_id"),
                    "checks_passed": a.get("checks_passed") if a.get("checks_passed") is not None else a.get("passed"),
                    "timings": {"duration_ms": a.get("avg_ms") or a.get("duration_ms")},
                }
                for i, a in enumerate(row["api_summary"])
            ]
        html_body = render_ui_report_html(
            run_id,
            ui_report=row.get("ui_report") if isinstance(row.get("ui_report"), dict) else None,
            status=str(row.get("status") or ""),
            service=str(row.get("service") or ""),
            traces=traces,
        ).encode("utf-8")
        return Response(content=html_body, media_type="text/html; charset=utf-8")

    raise HTTPException(status_code=404, detail="Artifact not found")


@app.get("/api/runs/{run_id}/playwright-trace")
async def api_run_playwright_trace(run_id: str):
    from fastapi.responses import FileResponse

    row = get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    path = Path(settings.data_dir) / "artifacts" / run_id / "playwright-trace.zip"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Playwright trace not available")
    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"{run_id}-playwright-trace.zip",
    )


@app.post("/smoke")
async def smoke() -> dict:
    cfg = ensure_default_config()
    record = await load_ops.run_test_from_config(cfg, triggered_by="manual")
    save_run(record)
    return record
