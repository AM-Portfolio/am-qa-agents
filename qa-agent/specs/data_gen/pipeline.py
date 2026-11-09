"""MCP/REST pipeline: import → gapfill → suite → workflows with handoff receipt."""
from __future__ import annotations

import asyncio
from typing import Any

from specs.data_gen.branch import resolve_branch_defaults
from specs.data_gen.import_svc import import_data_gen
from specs.data_gen.pack import disk_profile_for_suite
from specs.data_gen.suite import (
    activate_data_gen_set,
    api_ids_for_suite,
    ensure_suite_config,
    normalize_suite,
)
from specs.data_gen.workflows import list_data_gen_workflows


def _run_coro(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def data_gen_gapfill(
    *,
    service: str,
    environment: str,
    payload_set_version: int | None = None,
    allow_llm: bool = True,
    max_attempts: int = 3,
) -> dict[str, Any]:
    from specs.payloads.payload_pipeline import generate_all_payloads
    from specs.payloads.payload_store import set_active_payload_set

    if payload_set_version is not None:
        try:
            set_active_payload_set(service, int(payload_set_version))
        except Exception:  # noqa: BLE001
            pass
    out = _run_coro(
        generate_all_payloads(
            service=service,
            environment=environment,
            try_each=True,
            write_back=True,
            allow_llm=allow_llm,
            prefer_stored=True,
            max_attempts=max_attempts,
        )
    )
    failed = [
        str(r.get("api_id"))
        for r in (out.get("results") or [])
        if isinstance(r, dict) and not r.get("ok") and r.get("api_id")
    ]
    return {
        "ok": True,  # soft by default
        "service": service,
        "environment": environment,
        "payload_set_version": out.get("payload_set_version") or payload_set_version,
        "passed": out.get("passed"),
        "failed": out.get("failed"),
        "failed_api_ids": failed,
        "handoff": {
            "service": service,
            "environment": environment,
            "payload_set_version": out.get("payload_set_version") or payload_set_version,
            "passed": out.get("passed"),
            "failed_api_ids": failed,
        },
    }


def data_gen_run_suite(
    *,
    service: str,
    profile: str = "default",
    environment: str = "dev",
    case_kinds: list[str] | None = None,
    payload_set_version: int | None = None,
    wait: bool = False,
    triggered_by: str = "data_gen",
) -> dict[str, Any]:
    suite = normalize_suite(profile)
    disk = disk_profile_for_suite(suite)
    if payload_set_version is None:
        act = activate_data_gen_set(service, disk)
        if not act.get("ok"):
            return {**act, "run_ids": []}
        payload_set_version = int(act["payload_set_version"])
    else:
        from specs.payloads.payload_store import set_active_payload_set

        set_active_payload_set(service, int(payload_set_version))

    sel = api_ids_for_suite(
        service, suite, version=int(payload_set_version), case_kinds=case_kinds
    )
    if not sel.get("ok"):
        return {**sel, "run_ids": []}
    if not sel.get("selected_api_ids"):
        return {
            "ok": False,
            "error": "no_apis_selected",
            "message": "Suite filter selected zero APIs",
            "warnings": sel.get("warnings") or [],
            "run_ids": [],
            "payload_set_version": payload_set_version,
        }

    cfg = ensure_suite_config(
        service=service,
        suite=suite,
        environment=environment,
        payload_set_version=int(payload_set_version),
        selected_api_ids=list(sel["selected_api_ids"]),
        expects=dict(sel.get("expects") or {}),
    )
    from specs.security.acl import Caller
    from specs.services.execute_svc import execute_run_sync

    run = execute_run_sync(
        config_id=str(cfg.get("id") or ""),
        audience="developer",
        service=service,
        profile="debug",
        triggered_by=triggered_by,
        wait=wait,
        caller=Caller(role="developer"),
    )
    run_id = str((run or {}).get("id") or (run or {}).get("run_id") or "")
    ok = bool(run) and not (run or {}).get("error")
    return {
        "ok": ok,
        "service": service,
        "suite": suite,
        "environment": environment,
        "payload_set_version": payload_set_version,
        "selected_api_ids": sel["selected_api_ids"],
        "config_id": cfg.get("id"),
        "run_ids": [run_id] if run_id else [],
        "run": run,
        "warnings": sel.get("warnings") or [],
        "handoff": {
            "service": service,
            "profile": disk,
            "environment": environment,
            "payload_set_version": payload_set_version,
            "run_ids": [run_id] if run_id else [],
        },
    }


def data_gen_run_workflows(
    *,
    service: str,
    profile: str = "default",
    environment: str = "dev",
    flow_id: str | None = None,
    payload_set_version: int | None = None,
    strict_workflows: bool = False,
) -> dict[str, Any]:
    from specs.flows.runtime import suite_execute

    disk = disk_profile_for_suite(profile)
    rows = list_data_gen_workflows(service=service, profile=disk, flow_id=flow_id)
    flow_ids = [str(r.get("id")) for r in rows if r.get("id")]
    if not flow_ids:
        return {
            "ok": not strict_workflows,
            "skipped": True,
            "reason": "no_workflows",
            "execution_ids": [],
            "handoff": {"execution_ids": [], "service": service, "profile": disk},
        }
    try:
        out = suite_execute(
            flow_ids=flow_ids,
            env=environment,
            payload_set_version=payload_set_version,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": not strict_workflows,
            "error": str(exc),
            "execution_ids": [],
            "handoff": {"execution_ids": [], "error": str(exc)},
        }
    return {
        "ok": True,
        "service": service,
        "profile": disk,
        "execution_ids": out.get("execution_ids") or [],
        "suite_run_id": out.get("suite_run_id"),
        "count": out.get("count"),
        "handoff": {
            "service": service,
            "profile": disk,
            "execution_ids": out.get("execution_ids") or [],
            "suite_run_id": out.get("suite_run_id"),
        },
    }


def data_gen_pipeline(
    *,
    service: str | None = None,
    services: list[str] | None = None,
    profile: str | None = None,
    environment: str | None = None,
    git_ref: str | None = None,
    body: dict[str, Any] | None = None,
    pack_path: str | None = None,
    fill_gaps: bool = True,
    run_suite: bool = True,
    run_workflows: bool = True,
    strict_workflows: bool = False,
    strict_payloads: bool = False,
    allow_llm: bool | None = None,
    resume_from: str | None = None,
    prior_receipt: dict[str, Any] | None = None,
    wait_suite: bool = False,
) -> dict[str, Any]:
    defaults = resolve_branch_defaults(
        git_ref=git_ref, profile=profile, environment=environment
    )
    suite = defaults["suite"]
    env = defaults["environment"]
    disk = disk_profile_for_suite(suite)

    # LLM: default true on dig/dev, false on main/preprod CI unless set
    if allow_llm is None:
        allow_llm = env == "dev" and suite == "default"

    svc_list = [str(s).strip() for s in (services or []) if str(s).strip()]
    if service and str(service).strip():
        if str(service).strip() not in svc_list:
            svc_list.insert(0, str(service).strip())
    if not svc_list:
        return {"ok": False, "error": "service_required"}

    stages = ["import", "gapfill", "suite", "workflows"]
    start = (resume_from or "import").strip().lower()
    if start not in stages:
        start = "import"
    start_idx = stages.index(start)

    receipt: dict[str, Any] = dict(prior_receipt or {})
    receipt.update(
        {
            "suite": suite,
            "profile": disk,
            "environment": env,
            "git_ref": git_ref,
            "services": svc_list,
        }
    )
    per_service: list[dict[str, Any]] = list(receipt.get("per_service") or [])
    overall_ok = True

    for svc in svc_list:
        slot: dict[str, Any] = {"service": svc}
        # Find prior slot
        for prev in per_service:
            if prev.get("service") == svc:
                slot = dict(prev)
                break

        if start_idx <= stages.index("import"):
            imp = import_data_gen(
                service=svc,
                profile=suite,
                environment=env,
                body=body,
                pack_path=pack_path,
                make_active=True,
                sync_workflows=True,
            )
            slot["import"] = imp
            if not imp.get("ok"):
                overall_ok = False
                per_service = _upsert_slot(per_service, slot)
                continue
            slot["payload_set_version"] = imp.get("payload_set_version")

        ver = slot.get("payload_set_version") or (
            (slot.get("import") or {}).get("payload_set_version")
        )

        if fill_gaps and start_idx <= stages.index("gapfill"):
            gap = data_gen_gapfill(
                service=svc,
                environment=env,
                payload_set_version=int(ver) if ver is not None else None,
                allow_llm=bool(allow_llm),
            )
            slot["gapfill"] = gap
            if strict_payloads and (gap.get("failed") or 0) > 0:
                overall_ok = False
            ver = gap.get("payload_set_version") or ver
            slot["payload_set_version"] = ver

        if run_suite and start_idx <= stages.index("suite"):
            suite_out = data_gen_run_suite(
                service=svc,
                profile=suite,
                environment=env,
                payload_set_version=int(ver) if ver is not None else None,
                wait=wait_suite,
            )
            slot["suite"] = suite_out
            if not suite_out.get("ok"):
                overall_ok = False

        if run_workflows and start_idx <= stages.index("workflows"):
            wf = data_gen_run_workflows(
                service=svc,
                profile=disk,
                environment=env,
                payload_set_version=int(ver) if ver is not None else None,
                strict_workflows=strict_workflows,
            )
            slot["workflows"] = wf
            if strict_workflows and not wf.get("ok"):
                overall_ok = False

        per_service = _upsert_slot(per_service, slot)

    receipt["per_service"] = per_service
    receipt["ok"] = overall_ok
    receipt["handoff"] = {
        "receipt": True,
        "suite": suite,
        "profile": disk,
        "environment": env,
        "services": svc_list,
        "payload_set_versions": {
            s["service"]: s.get("payload_set_version") for s in per_service
        },
    }
    return receipt


def _upsert_slot(rows: list[dict[str, Any]], slot: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    found = False
    for r in rows:
        if r.get("service") == slot.get("service"):
            out.append(slot)
            found = True
        else:
            out.append(r)
    if not found:
        out.append(slot)
    return out
