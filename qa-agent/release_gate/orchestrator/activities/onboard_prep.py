"""Service onboard prep activities — Specs analyze → OpenAPI → tools → smoke → overview."""

from __future__ import annotations

import base64
import json
import time
from typing import Any
from urllib.parse import urlparse

from temporalio import activity

from orchestrator.activities.onboard_report import (
    apis_tools_parity,
    classify_smoke_failure,
    make_step,
    normalize_env,
    persist_latest_report,
    timed_ms,
)


def _jwt_claims(token: str) -> dict[str, Any]:
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        pad = "=" * (-len(parts[1]) % 4)
        raw = base64.urlsafe_b64decode(parts[1] + pad)
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _plugin_id_for_service(service: str, explicit: str | None) -> str | None:
    if explicit:
        return explicit
    try:
        from ui_evidence.plugins.loader import list_plugins

        for row in list_plugins(include_disabled=True):
            if str(row.get("spt_service_id") or "") == service or str(row.get("id") or "") == service:
                return str(row.get("id") or "")
    except Exception:  # noqa: BLE001
        return None
    return None


def _data_dir() -> str:
    try:
        from specs.config import settings

        return str(settings.data_dir or "/data")
    except Exception:  # noqa: BLE001
        return "/data"


@activity.defn(name="activity_onboard_analyze")
async def activity_onboard_analyze(args: dict[str, Any]) -> dict[str, Any]:
    from specs.catalog.catalog_loader import load_registration, reachable_target_for_service

    t0 = time.monotonic()
    service = str(args.get("service") or "").strip()
    env = normalize_env(args.get("environment"))
    if not service:
        return make_step(
            "analyze",
            ok=False,
            status="missing_service",
            error="service required",
            duration_ms=timed_ms(t0),
        )
    reg = load_registration(service)
    if not reg:
        return make_step(
            "analyze",
            ok=False,
            status="registration_missing",
            error=f"no spt.yaml registration for {service}",
            evidence={"service": service, "environment": env},
            duration_ms=timed_ms(t0),
        )
    target = reachable_target_for_service(service, env)
    if not target or not str(target).startswith("http"):
        return make_step(
            "analyze",
            ok=False,
            status="target_unreachable",
            error="no reachable target URL",
            evidence={"service": service, "environment": env, "registration": bool(reg)},
            duration_ms=timed_ms(t0),
        )
    return make_step(
        "analyze",
        ok=True,
        status="ok",
        evidence={
            "service": service,
            "environment": env,
            "target_url": target,
            "runtime": reg.get("runtime"),
            "label": reg.get("label") or service,
        },
        duration_ms=timed_ms(t0),
    )


@activity.defn(name="activity_onboard_openapi_sync")
async def activity_onboard_openapi_sync(args: dict[str, Any]) -> dict[str, Any]:
    from specs.catalog.openapi_sync import sync_openapi_for_service

    t0 = time.monotonic()
    service = str(args.get("service") or "").strip()
    env = normalize_env(args.get("environment"))
    try:
        out = sync_openapi_for_service(service, env, force=True)
    except Exception as exc:  # noqa: BLE001
        return make_step(
            "openapi_sync",
            ok=False,
            status="openapi_unavailable",
            error=str(exc),
            evidence={"service": service, "environment": env},
            duration_ms=timed_ms(t0),
        )
    if not out.get("ok"):
        return make_step(
            "openapi_sync",
            ok=False,
            status="openapi_unavailable",
            error=str(out.get("error") or "openapi_unavailable"),
            evidence={
                "target_url": args.get("target_url"),
                "openapi_url": out.get("openapi_url"),
                "service": service,
                "environment": env,
            },
            duration_ms=timed_ms(t0),
        )
    return make_step(
        "openapi_sync",
        ok=True,
        status="ok",
        evidence={
            "openapi_url": out.get("openapi_url"),
            "source": out.get("source"),
            "path_count": out.get("path_count"),
            "operation_count": out.get("operation_count"),
            "stale": out.get("stale"),
            "live_error": out.get("live_error"),
        },
        duration_ms=timed_ms(t0),
    )


@activity.defn(name="activity_onboard_apis")
async def activity_onboard_apis(args: dict[str, Any]) -> dict[str, Any]:
    from specs.catalog.catalog_loader import load_service_apis

    t0 = time.monotonic()
    service = str(args.get("service") or "").strip()
    env = normalize_env(args.get("environment"))
    data = load_service_apis(service, env)
    apis = [a for a in (data.get("apis") or []) if isinstance(a, dict)]
    source = str(data.get("source") or "")
    real = [
        a
        for a in apis
        if "/health" not in str(a.get("path") or "").lower()
        and str(a.get("id") or "") != "actuator.health"
    ]
    if source == "health-fallback" or not real:
        return make_step(
            "apis_catalog",
            ok=False,
            status="apis_health_fallback",
            error="only health-fallback ops (no real OpenAPI operations)",
            evidence={
                "source": source,
                "api_count": len(apis),
                "real_count": len(real),
                "openapi_error": data.get("openapi_error"),
                "openapi_url": data.get("openapi_url"),
            },
            duration_ms=timed_ms(t0),
        )
    return make_step(
        "apis_catalog",
        ok=True,
        status="ok",
        evidence={
            "source": source,
            "api_count": len(real),
            "total_including_health": len(apis),
            "openapi_url": data.get("openapi_url"),
        },
        duration_ms=timed_ms(t0),
    )


@activity.defn(name="activity_onboard_tools_refresh")
async def activity_onboard_tools_refresh(args: dict[str, Any]) -> dict[str, Any]:
    from specs.catalog.catalog_loader import load_openapi_document, load_service_apis, reachable_target_for_service
    from specs.openapi_tools.registry import list_tools, tools_from_openapi_document

    t0 = time.monotonic()
    service = str(args.get("service") or "").strip()
    env = normalize_env(args.get("environment"))
    meta = load_openapi_document(service, env)
    doc = meta.get("document") if isinstance(meta.get("document"), dict) else None
    target = reachable_target_for_service(service, env)
    if not doc:
        return make_step(
            "tools_refresh",
            ok=False,
            status="openapi_doc_missing",
            error=str(meta.get("error") or "no openapi document"),
            evidence={"service": service, "environment": env},
            duration_ms=timed_ms(t0),
        )
    built = tools_from_openapi_document(
        doc,
        service=service,
        base_url=target or "",
        environment=env,
        persist=True,
    )
    tools = list(list_tools(service=service, limit=2000).get("tools") or [])
    apis = [
        a
        for a in (load_service_apis(service, env).get("apis") or [])
        if isinstance(a, dict)
    ]
    parity = apis_tools_parity(apis, tools)
    ok = bool(built.get("count")) and parity.get("ok")
    return make_step(
        "tools_refresh",
        ok=ok,
        status="ok" if ok else "tools_apis_parity_failed",
        error=None if ok else "apis↔tools method+path mismatch or empty tools",
        evidence={
            "tool_count": built.get("count") or len(tools),
            "operation_count": built.get("operation_count"),
            "parity": parity,
        },
        duration_ms=timed_ms(t0),
    )


@activity.defn(name="activity_onboard_contract")
async def activity_onboard_contract(args: dict[str, Any]) -> dict[str, Any]:
    from specs.catalog.catalog_loader import load_service_apis
    from specs.openapi_tools.registry import list_tools

    t0 = time.monotonic()
    service = str(args.get("service") or "").strip()
    env = normalize_env(args.get("environment"))
    plugin_id = _plugin_id_for_service(service, args.get("plugin_id"))
    evidence: dict[str, Any] = {"plugin_id": plugin_id, "service": service, "environment": env}

    if plugin_id:
        try:
            from ui_evidence.plugins.onboard import contract_smoke

            smoke = contract_smoke(plugin_id, env)
            evidence["contract_smoke"] = {
                k: smoke.get(k)
                for k in ("ok", "status", "tool_count", "min_tools", "openapi_hash", "error")
            }
            if not smoke.get("ok"):
                return make_step(
                    "contract",
                    ok=False,
                    status=str(smoke.get("status") or "onboard_blocked"),
                    error=str(smoke.get("error") or f"min_tools not met"),
                    evidence=evidence,
                    duration_ms=timed_ms(t0),
                )
        except Exception as exc:  # noqa: BLE001
            return make_step(
                "contract",
                ok=False,
                status="contract_smoke_error",
                error=str(exc),
                evidence=evidence,
                duration_ms=timed_ms(t0),
            )

    apis = [a for a in (load_service_apis(service, env).get("apis") or []) if isinstance(a, dict)]
    tools = list(list_tools(service=service, limit=2000).get("tools") or [])
    parity = apis_tools_parity(apis, tools)
    evidence["parity"] = parity
    if not parity.get("ok"):
        return make_step(
            "contract",
            ok=False,
            status="parity_failed",
            error="apis↔tools parity failed",
            evidence=evidence,
            duration_ms=timed_ms(t0),
        )
    return make_step(
        "contract",
        ok=True,
        status="ok",
        evidence=evidence,
        duration_ms=timed_ms(t0),
    )


@activity.defn(name="activity_onboard_auth")
async def activity_onboard_auth(args: dict[str, Any]) -> dict[str, Any]:
    from specs.catalog.catalog_loader import platform_bearer_token

    t0 = time.monotonic()
    env = normalize_env(args.get("environment"))
    try:
        token = platform_bearer_token(environment=env)
    except Exception as exc:  # noqa: BLE001
        return make_step(
            "auth_try_token",
            ok=False,
            status="identity_unavailable",
            error=str(exc),
            evidence={"environment": env},
            duration_ms=timed_ms(t0),
            hard_fail=True,
        )
    if not token:
        return make_step(
            "auth_try_token",
            ok=False,
            status="identity_unavailable",
            error="no bearer token from platform identity",
            evidence={"environment": env},
            duration_ms=timed_ms(t0),
            hard_fail=True,
        )
    claims = _jwt_claims(token)
    iss = str(claims.get("iss") or "")
    iss_host = urlparse(iss).hostname or iss
    # Soft sanity: iss should mention asrax / keycloak-ish host when present
    evidence = {
        "environment": env,
        "iss": iss,
        "iss_host": iss_host,
        "has_sub": bool(claims.get("sub")),
        "token_len": len(token),
    }
    return make_step(
        "auth_try_token",
        ok=True,
        status="ok",
        evidence=evidence,
        duration_ms=timed_ms(t0),
    )


@activity.defn(name="activity_onboard_prepare_mcp")
async def activity_onboard_prepare_mcp(args: dict[str, Any]) -> dict[str, Any]:
    from specs.payloads.payload_pipeline import prepare_mcp_payloads_for_service

    t0 = time.monotonic()
    service = str(args.get("service") or "").strip()
    env = normalize_env(args.get("environment"))
    try:
        out = prepare_mcp_payloads_for_service(
            service=service,
            environment=env,
            write_overlays=True,
            try_each=False,
        )
    except Exception as exc:  # noqa: BLE001
        return make_step(
            "prepare_mcp",
            ok=False,
            status="prepare_mcp_error",
            error=str(exc),
            evidence={"service": service, "environment": env},
            duration_ms=timed_ms(t0),
            hard_fail=False,
        )
    mapped = out.get("mapped") if isinstance(out.get("mapped"), list) else []
    mapped_count = len(mapped)
    warn = mapped_count == 0
    return make_step(
        "prepare_mcp",
        ok=True,
        status="warn_mapped_empty" if warn else "ok",
        error="mapped_count=0" if warn else None,
        evidence={
            "mapped_count": mapped_count,
            "skipped_count": len(out.get("skipped") or []),
            "ok": out.get("ok"),
            "error": out.get("error"),
        },
        duration_ms=timed_ms(t0),
        hard_fail=False,
    )


@activity.defn(name="activity_onboard_generate_payloads")
async def activity_onboard_generate_payloads(args: dict[str, Any]) -> dict[str, Any]:
    from specs.payloads.payload_pipeline import generate_all_payloads

    t0 = time.monotonic()
    service = str(args.get("service") or "").strip()
    env = normalize_env(args.get("environment"))
    allow_llm = bool(args.get("allow_llm", True))
    strict_payloads = bool(args.get("strict_payloads"))
    try:
        out = await generate_all_payloads(
            service=service,
            environment=env,
            try_each=True,
            write_back=True,
            allow_llm=allow_llm,
            prefer_stored=True,
            max_attempts=int(args.get("max_attempts") or 3),
        )
    except Exception as exc:  # noqa: BLE001
        return make_step(
            "generate_all_payloads",
            ok=False,
            status="generate_failed",
            error=str(exc),
            evidence={"service": service, "environment": env},
            duration_ms=timed_ms(t0),
            hard_fail=True,
        )
    total = int(out.get("total") or 0)
    passed = int(out.get("passed") or 0)
    failed = int(out.get("failed") or 0)
    # Started successfully if we have rows; per-API failures soft unless strict
    started = total > 0
    if not started:
        return make_step(
            "generate_all_payloads",
            ok=False,
            status="no_apis",
            error="generate_all produced zero API rows",
            evidence=out,
            duration_ms=timed_ms(t0),
            hard_fail=True,
        )
    hard = bool(strict_payloads and failed > 0)
    ok = failed == 0 or not strict_payloads
    return make_step(
        "generate_all_payloads",
        ok=ok if not hard else False,
        status="ok" if failed == 0 else ("payloads_strict_fail" if hard else "payloads_partial"),
        error=None if failed == 0 else f"{failed}/{total} APIs failed",
        evidence={
            "total": total,
            "passed": passed,
            "failed": failed,
            "payload_set_version": out.get("payload_set_version"),
            "llm_rows": sum(1 for r in (out.get("results") or []) if r.get("llm_attempted")),
        },
        duration_ms=timed_ms(t0),
        hard_fail=hard,
    )


@activity.defn(name="activity_onboard_llm_status")
async def activity_onboard_llm_status(args: dict[str, Any]) -> dict[str, Any]:
    t0 = time.monotonic()
    allow_llm = bool(args.get("allow_llm", True))
    llm_rows = int(args.get("llm_rows") or 0)
    try:
        from specs.config import settings

        flag = bool(getattr(settings, "spt_payload_llm_fallback", False))
    except Exception:  # noqa: BLE001
        flag = False
    probe: dict[str, Any] = {}
    try:
        from ui_evidence.scenario_bank.llm_status import probe_litellm

        probe = probe_litellm(ping_chat=False)
    except Exception as exc:  # noqa: BLE001
        probe = {"available": False, "error": str(exc)}
    if not allow_llm:
        status = "skipped_allow_llm_false"
    elif not flag and not probe.get("available"):
        status = "disabled_or_upstream"
    elif probe.get("available"):
        status = "ok"
    else:
        status = "upstream_unavailable"
    return make_step(
        "llm_fallback",
        ok=True,
        status=status,
        evidence={
            "allow_llm": allow_llm,
            "spt_payload_llm_fallback": flag,
            "llm_attempted_rows": llm_rows,
            "litellm_available": probe.get("available"),
            "litellm_error": probe.get("error"),
            "model": probe.get("model"),
        },
        duration_ms=timed_ms(t0),
        hard_fail=False,
    )


@activity.defn(name="activity_onboard_tools_smoke")
async def activity_onboard_tools_smoke(args: dict[str, Any]) -> dict[str, Any]:
    from specs.openapi_tools.registry import call_tool, list_tools

    t0 = time.monotonic()
    service = str(args.get("service") or "").strip()
    env = normalize_env(args.get("environment"))
    strict_smoke = bool(args.get("strict_smoke"))
    tools = list(list_tools(service=service, limit=2000).get("tools") or [])
    if not tools:
        return make_step(
            "tools_smoke",
            ok=False,
            status="no_tools",
            error="no tools registered for smoke",
            evidence={"service": service},
            duration_ms=timed_ms(t0),
            hard_fail=True,
        )

    def _pick(pred) -> dict[str, Any] | None:
        for t in tools:
            if pred(t):
                return t
        return None

    health = _pick(lambda t: "health" in str(t.get("path") or "").lower())
    read = _pick(
        lambda t: str(t.get("method") or "").upper() == "GET"
        and "health" not in str(t.get("path") or "").lower()
        and (
            "/subscriptions/me" in str(t.get("path") or "")
            or str(t.get("path") or "").count("{") == 0
        )
    )
    if read is None:
        read = _pick(lambda t: str(t.get("method") or "").upper() == "GET")

    calls: list[dict[str, Any]] = []
    hard_fail = False
    status = "ok"
    error: str | None = None

    for label, row in (("health", health), ("read", read)):
        if not row:
            continue
        name = str(row.get("name") or "")
        result = call_tool(name, {}, with_identity_auth=True, record_run=False, environment=env)
        entry = {
            "label": label,
            "tool": name,
            "path": row.get("path"),
            "ok": bool(result.get("ok")),
            "status": result.get("status"),
            "error": result.get("error"),
        }
        calls.append(entry)
        if result.get("ok"):
            continue
        h, st, err = classify_smoke_failure(result, strict_smoke=strict_smoke)
        entry["classify"] = st
        if h:
            hard_fail = True
            status = st
            error = err
            break
        status = st
        error = err

    ok = not hard_fail and (status == "ok" or status == "billing_dependency" or status == "smoke_soft_failure")
    # Soft Lago: ok stays True with warning status
    if status in {"billing_dependency", "smoke_soft_failure"} and not hard_fail:
        ok = True
    return make_step(
        "tools_smoke",
        ok=ok and not hard_fail,
        status=status if (hard_fail or error) else "ok",
        error=error,
        evidence={"calls": calls, "strict_smoke": strict_smoke},
        duration_ms=timed_ms(t0),
        hard_fail=hard_fail,
    )


@activity.defn(name="activity_onboard_overview")
async def activity_onboard_overview(args: dict[str, Any]) -> dict[str, Any]:
    from specs.services.service_overview import build_service_overview

    t0 = time.monotonic()
    service = str(args.get("service") or "").strip()
    env = normalize_env(args.get("environment"))
    warnings = list(args.get("warnings") or [])
    try:
        ov = build_service_overview(
            service,
            environment=env,
            runs_limit=10,
            live_openapi=False,
        )
    except Exception as exc:  # noqa: BLE001
        return make_step(
            "overview_report",
            ok=True,
            status="overview_error",
            error=str(exc),
            evidence={"warnings": warnings},
            duration_ms=timed_ms(t0),
            hard_fail=False,
        )
    return make_step(
        "overview_report",
        ok=True,
        status="ok",
        evidence={
            "warnings": warnings,
            "api_count": ov.get("api_count") or (ov.get("apis") or {}).get("count"),
            "payload_set_version": (ov.get("payloads") or {}).get("active_version")
            or (ov.get("payload_set") or {}).get("version"),
            "overview_keys": sorted(list(ov.keys()))[:30],
        },
        duration_ms=timed_ms(t0),
        hard_fail=False,
    )


@activity.defn(name="activity_onboard_persist_report")
async def activity_onboard_persist_report(args: dict[str, Any]) -> dict[str, Any]:
    report = args.get("report") if isinstance(args.get("report"), dict) else {}
    service = str(report.get("service") or args.get("service") or "").strip()
    env = normalize_env(report.get("environment") or args.get("environment"))
    path = persist_latest_report(_data_dir(), service, env, report)
    return {"ok": True, "path": path}
