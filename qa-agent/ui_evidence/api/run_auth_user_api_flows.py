"""Execute detailed auth/user/subscription API flows; write HTML/JSON report."""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ui_evidence.api.auth_identity_profiles import resolve_tool_for_scenario
from ui_evidence.api.auth_user_api_flows import AUTH_USER_API_FLOWS
from ui_evidence.api.ephemeral_identity import disable_user, force_verify_email
from ui_evidence.api.flow_metrics import (
    build_hotspots,
    default_ledger_path,
    load_ledger,
    merge_flow_results_into_ledger,
    render_hotspots_html,
    save_ledger,
)
from ui_evidence.api.growthbook_flags import ephemeral_user_flows_enabled

logger = logging.getLogger(__name__)

_IDENTITY_BASE_DEFAULT = "https://am.asrax.in/identity"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _legacy_mutations_allowed() -> bool:
    if (os.environ.get("FLOW_ALLOW_MUTATIONS") or "").strip() not in {"1", "true", "yes"}:
        return False
    env = (
        os.environ.get("APP_ENV")
        or os.environ.get("SPT_DEFAULT_ENVIRONMENT")
        or os.environ.get("ENVIRONMENT")
        or "prod"
    ).lower()
    return env not in {"prod", "production"}


def _identity_base(tools: list[dict[str, Any]]) -> str:
    env_base = (os.environ.get("SPT_IDENTITY_URL") or "").rstrip("/")
    if env_base:
        return env_base
    for t in tools:
        meta = t.get("_meta") if isinstance(t.get("_meta"), dict) else None
        if meta and meta.get("base_url"):
            return str(meta["base_url"]).rstrip("/")
        if t.get("base_url"):
            return str(t["base_url"]).rstrip("/")
    return _IDENTITY_BASE_DEFAULT


def _resolve_tool(tools: list[dict[str, Any]], step: dict[str, Any]) -> dict[str, Any] | None:
    exact = str(step.get("exact_path") or "")
    method = str(step.get("method") or "").lower()
    if exact:
        for t in tools:
            if str(t.get("path") or "") == exact and str(t.get("method") or "").lower() == method:
                return t
    return resolve_tool_for_scenario(
        tools,
        {
            "path_contains": step.get("path_contains"),
            "method": method,
            "tool_match": step.get("tool_match") or [],
        },
    )


def _tool_meta(tool: dict[str, Any] | None, *, svc: str, step: dict[str, Any], base: str) -> dict[str, Any]:
    from specs.openapi_tools.registry import _TOOLS

    if tool:
        cached = _TOOLS.get(str(tool.get("name") or ""))
        if cached and isinstance(cached.get("_meta"), dict):
            return dict(cached["_meta"])
        return {
            "method": tool.get("method") or step.get("method"),
            "path": tool.get("path") or step.get("exact_path") or step.get("path_contains"),
            "base_url": base,
            "op_id": tool.get("op_id"),
            "service": svc,
            "tool_name": tool.get("name"),
        }
    return {
        "method": step.get("method"),
        "path": step.get("exact_path") or step.get("path_contains"),
        "base_url": str(step.get("base_url_override") or base).rstrip("/"),
        "op_id": f"raw_{step.get('id')}",
        "service": svc,
        "tool_name": f"raw_{step.get('id')}",
    }


def run_auth_user_api_flows(
    *,
    environment: str = "prod",
    refresh: bool = True,
    report_dir: Path | None = None,
) -> dict[str, Any]:
    from specs.openapi_tools.generator import execute_openapi_tool_sync
    from specs.openapi_tools.registry import (
        call_tool,
        list_tools,
        refresh_tools_from_prod,
    )
    from specs.catalog.catalog_loader import _platform_openapi_headers

    flag = ephemeral_user_flows_enabled(environment)
    ephemeral_on = bool(flag.get("enabled"))
    legacy_mut = _legacy_mutations_allowed()

    services = ["am-identity", "am-subscription", "am-user-platform"]
    refresh_info: dict[str, Any] = {}
    if refresh:
        refresh_info = refresh_tools_from_prod(
            environment=environment, services=services
        )

    tools_by_svc: dict[str, list[dict[str, Any]]] = {}
    for svc in services:
        tools_by_svc[svc] = list(list_tools(service=svc, limit=1000).get("tools") or [])

    spt_user = os.environ.get("SPT_AUTH_USERNAME") or ""
    spt_password = os.environ.get("SPT_AUTH_PASSWORD") or ""
    identity_base = _identity_base(tools_by_svc.get("am-identity") or [])

    flow_results: list[dict[str, Any]] = []
    access_token: str | None = None
    refresh_token: str | None = None
    ephemeral: dict[str, str] = {}

    for flow in AUTH_USER_API_FLOWS:
        gate = str(flow.get("gate") or "prod_safe")
        if gate == "ephemeral_user" and not ephemeral_on and not legacy_mut:
            flow_results.append(
                {
                    "id": flow["id"],
                    "title": flow.get("title"),
                    "status": "SKIPPED",
                    "reason": (
                        f"GrowthBook flag {flag.get('key')} off "
                        f"(source={flag.get('source')})"
                    ),
                    "gate": gate,
                    "steps": [],
                }
            )
            continue
        if gate == "nonprod_only" and not legacy_mut and not ephemeral_on:
            flow_results.append(
                {
                    "id": flow["id"],
                    "title": flow.get("title"),
                    "status": "SKIPPED",
                    "reason": "nonprod_only — enable FLOW_ALLOW_MUTATIONS or GrowthBook ephemeral flag",
                    "gate": gate,
                    "steps": [],
                }
            )
            continue

        # Alias flow: mark discovered when setup already ran
        if flow.get("alias_of"):
            setup = next(
                (f for f in flow_results if f.get("id") == flow["alias_of"]),
                None,
            )
            flow_results.append(
                {
                    "id": flow["id"],
                    "title": flow.get("title"),
                    "gate": gate,
                    "status": setup.get("status") if setup else "SKIPPED",
                    "alias_of": flow["alias_of"],
                    "steps": [
                        {
                            "id": "register_alias",
                            "status": "DISCOVERED",
                            "path": "/auth/register",
                            "note": (
                                f"see {flow['alias_of']} "
                                f"({(setup or {}).get('status', 'pending')})"
                            ),
                        }
                    ],
                }
            )
            continue

        step_rows: list[dict[str, Any]] = []
        flow_failed = False
        for step in flow.get("steps") or []:
            t0 = time.perf_counter()

            def _add(row: dict[str, Any], _t0: float = t0) -> None:
                row["duration_ms"] = round((time.perf_counter() - _t0) * 1000, 1)
                step_rows.append(row)

            sid = str(step.get("id") or "")
            kind = str(step.get("kind") or "call_tool")
            svc = str(step.get("service") or "am-identity")
            tools = tools_by_svc.get(svc) or []
            tool = _resolve_tool(tools, step)

            if kind == "discover":
                _add(
                    {
                        "id": sid,
                        "status": "DISCOVERED" if tool else "MISSING",
                        "tool": (tool or {}).get("name"),
                        "path": (tool or {}).get("path") or step.get("path_contains"),
                        "note": step.get("note"),
                    }
                )
                continue

            if kind == "keycloak_force_verify":
                if not ephemeral.get("email"):
                    _add(
                        {
                            "id": sid,
                            "status": "SKIPPED",
                            "reason": "no ephemeral email from register",
                        }
                    )
                    continue
                kv = force_verify_email(
                    email=ephemeral["email"],
                    user_id=ephemeral.get("user_id") or None,
                )
                if kv.get("ok"):
                    ephemeral["verified"] = "1"
                    if kv.get("user_id"):
                        ephemeral["user_id"] = str(kv["user_id"])
                    _add(
                        {
                            "id": sid,
                            "status": "PASSED",
                            "note": step.get("note"),
                            "http_status": kv.get("http_status"),
                        }
                    )
                else:
                    _add(
                        {
                            "id": sid,
                            "status": "EXPECTED",
                            "reason": kv.get("reason"),
                            "note": step.get("note"),
                        }
                    )
                continue

            if kind == "keycloak_disable":
                if not ephemeral.get("email"):
                    _add(
                        {
                            "id": sid,
                            "status": "SKIPPED",
                            "reason": "no ephemeral email",
                        }
                    )
                    continue
                # Skip if request_deletion already passed in this flow
                if any(
                    s.get("id") == "request_deletion" and s.get("status") == "PASSED"
                    for s in step_rows
                ):
                    _add(
                        {
                            "id": sid,
                            "status": "SKIPPED",
                            "reason": "request_deletion already succeeded",
                        }
                    )
                    continue
                kd = disable_user(
                    email=ephemeral["email"],
                    user_id=ephemeral.get("user_id") or None,
                )
                status = "PASSED" if kd.get("ok") else (
                    "SKIPPED" if step.get("optional_service") else "FAILED"
                )
                if status == "FAILED":
                    flow_failed = True
                _add(
                    {
                        "id": sid,
                        "status": status,
                        "reason": None if kd.get("ok") else kd.get("reason"),
                        "http_status": kd.get("http_status"),
                        "note": step.get("note"),
                    }
                )
                continue

            if kind != "raw_http" and not tool:
                # Identity paths: fall back to raw HTTP when OpenAPI registry is empty
                path_hint = step.get("exact_path") or step.get("path_contains")
                if svc == "am-identity" and path_hint and step.get("method"):
                    kind = "raw_http"
                else:
                    status = "SKIPPED" if step.get("optional_service") else "FAILED"
                    _add(
                        {
                            "id": sid,
                            "status": status,
                            "reason": "no OpenAPI tool (service swagger may be HTML/unavailable)",
                            "path": path_hint,
                        }
                    )
                    if status == "FAILED":
                        flow_failed = True
                    continue

            args: dict[str, Any] = {}
            if isinstance(step.get("payload"), dict):
                args.update(step["payload"])
            if isinstance(step.get("payload_from_env"), dict):
                for key, env_name in step["payload_from_env"].items():
                    val = (os.environ.get(str(env_name)) or "").strip()
                    if val:
                        args[str(key)] = val

            eph_ready = bool(
                ephemeral.get("email")
                and ephemeral.get("password")
                and (ephemeral.get("verified") or ephemeral.get("access_token"))
            )
            use_eph = bool(
                step.get("uses_ephemeral_creds")
                or (step.get("prefer_ephemeral_creds") and eph_ready)
            )
            if step.get("uses_unique_register_payload"):
                uniq = f"qa+api{int(time.time())}@asrax.in"
                pwd = "QaFlow!23456"
                args = {
                    "email": uniq,
                    "password": pwd,
                    "first_name": "QA",
                    "last_name": "Ephemeral",
                }
                ephemeral["email"] = uniq
                ephemeral["password"] = pwd
            elif step.get("uses_ephemeral_email_body"):
                if ephemeral.get("verified"):
                    _add(
                        {
                            "id": sid,
                            "status": "SKIPPED",
                            "reason": "already force-verified via Keycloak",
                        }
                    )
                    continue
                if not ephemeral.get("email"):
                    _add(
                        {
                            "id": sid,
                            "status": "SKIPPED",
                            "reason": "no ephemeral email",
                        }
                    )
                    continue
                args = {"email": ephemeral["email"]}
            elif use_eph:
                if not ephemeral.get("email"):
                    _add(
                        {
                            "id": sid,
                            "status": "SKIPPED",
                            "reason": "no ephemeral user — FLOW_EPHEMERAL_SETUP failed or skipped",
                        }
                    )
                    continue
                args = {
                    "username": ephemeral["email"],
                    "password": ephemeral["password"],
                }
            elif step.get("uses_spt_auth_creds"):
                args = {"username": spt_user, "password": spt_password}
            elif step.get("uses_spt_email_only"):
                email = (
                    ephemeral.get("email")
                    if step.get("prefer_ephemeral_email") and ephemeral.get("email")
                    else spt_user
                )
                args = {"email": email}
            elif step.get("uses_refresh_token"):
                if not refresh_token:
                    _add(
                        {
                            "id": sid,
                            "status": "SKIPPED",
                            "reason": "no refresh_token from prior login",
                        }
                    )
                    continue
                args = {"refresh_token": refresh_token}
            elif step.get("uses_access_token_body") and access_token:
                args = {"refresh_token": refresh_token} if refresh_token else {}

            headers = {"Accept": "application/json"}
            if step.get("auth") or step.get("uses_access_token_body"):
                if access_token:
                    headers["Authorization"] = f"Bearer {access_token}"
                else:
                    headers.update(_platform_openapi_headers())

            method = str(
                (tool or {}).get("method") or step.get("method") or "get"
            ).lower()
            base = str(step.get("base_url_override") or identity_base).rstrip("/")
            meta = _tool_meta(tool, svc=svc, step=step, base=base)

            if kind == "raw_http" or method == "delete":
                out = execute_openapi_tool_sync(meta, args, headers=headers)
            elif access_token and (step.get("auth") or step.get("uses_access_token_body") or use_eph):
                out = execute_openapi_tool_sync(dict(meta), args, headers=headers)
            elif use_eph or step.get("uses_unique_register_payload"):
                out = execute_openapi_tool_sync(dict(meta), args, headers=headers)
            else:
                out = call_tool(
                    str(tool["name"]),
                    args,
                    with_identity_auth=bool(step.get("auth")),
                    record_run=True,
                )

            http = int(out.get("status") or 0)
            ok = bool(out.get("ok"))
            if step.get("capture_tokens") and ok and isinstance(out.get("body"), dict):
                body = out["body"]
                access_token = body.get("access_token") or access_token
                refresh_token = body.get("refresh_token") or refresh_token
                if ephemeral:
                    ephemeral["access_token"] = access_token or ""
                    ephemeral["refresh_token"] = refresh_token or ""
            if step.get("capture_ephemeral_creds") and ok:
                if isinstance(out.get("body"), dict):
                    body = out["body"]
                    if body.get("id"):
                        ephemeral["user_id"] = str(body["id"])
                    if body.get("access_token"):
                        access_token = body["access_token"]
                        ephemeral["access_token"] = access_token
                    if body.get("refresh_token"):
                        refresh_token = body["refresh_token"]
                        ephemeral["refresh_token"] = refresh_token

            detail = ""
            if isinstance(out.get("body"), dict):
                detail = str(out["body"].get("detail") or "")
            elif isinstance(out.get("body"), str):
                detail = out["body"]

            if ok:
                status = "PASSED"
            elif http >= 500 and step.get("allow_5xx_as_defect"):
                status = "FAILED"
                flow_failed = True
            elif http == 403 and "verify" in detail.lower():
                status = "EXPECTED"
            elif http in (401, 403) or (
                400 <= http < 500 and step.get("allow_4xx_as_expected")
            ):
                status = "EXPECTED"
            elif step.get("optional_service") and not ok:
                status = "SKIPPED"
            elif not ok:
                status = "FAILED"
                flow_failed = True
            else:
                status = "PASSED"

            _add(
                {
                    "id": sid,
                    "status": status,
                    "tool": (tool or {}).get("name") or meta.get("tool_name"),
                    "path": meta.get("path"),
                    "method": method.upper(),
                    "http_status": http,
                    "url": out.get("url"),
                    "note": step.get("note"),
                    "error": out.get("error"),
                }
            )

        called = [
            s
            for s in step_rows
            if s.get("status") not in {"SKIPPED", "DISCOVERED", "MISSING"}
        ]
        # Cleanup success = identity deletion OR Keycloak disable
        if flow.get("id") == "FLOW_EPHEMERAL_CLEANUP":
            cleaned = any(
                s.get("id") in {"request_deletion", "keycloak_disable"}
                and s.get("status") == "PASSED"
                for s in step_rows
            )
            if cleaned:
                flow_failed = False
        if flow_failed:
            flow_status = "FAILED"
        elif not called and step_rows:
            flow_status = "SKIPPED"
        else:
            flow_status = "PASSED"
        flow_results.append(
            {
                "id": flow["id"],
                "title": flow.get("title"),
                "gate": gate,
                "status": flow_status,
                "steps": step_rows,
            }
        )

    # Safety net: if setup created a user but cleanup flow was skipped/failed, try once more
    cleanup_status = next(
        (f.get("status") for f in flow_results if f.get("id") == "FLOW_EPHEMERAL_CLEANUP"),
        None,
    )
    safety_cleanup: dict[str, Any] | None = None
    if ephemeral.get("email") and ephemeral.get("password") and cleanup_status != "PASSED":
        try:
            login_out = execute_openapi_tool_sync(
                {
                    "method": "post",
                    "path": "/auth/login",
                    "base_url": identity_base,
                    "service": "am-identity",
                    "tool_name": "safety_login",
                    "op_id": "safety_login",
                },
                {"username": ephemeral["email"], "password": ephemeral["password"]},
                headers={"Accept": "application/json"},
            )
            tok = None
            if login_out.get("ok") and isinstance(login_out.get("body"), dict):
                tok = login_out["body"].get("access_token")
            if tok:
                del_out = execute_openapi_tool_sync(
                    {
                        "method": "post",
                        "path": "/users/me/request-deletion",
                        "base_url": identity_base,
                        "service": "am-identity",
                        "tool_name": "safety_cleanup",
                        "op_id": "safety_cleanup",
                    },
                    {"feedback": "qa-auth-ephemeral-user-flows safety cleanup"},
                    headers={
                        "Accept": "application/json",
                        "Authorization": f"Bearer {tok}",
                    },
                )
                safety_cleanup = {
                    "login_status": login_out.get("status"),
                    "deletion_status": del_out.get("status"),
                    "ok": bool(del_out.get("ok")),
                }
        except Exception as exc:  # noqa: BLE001
            safety_cleanup = {"ok": False, "error": str(exc)}

    counts = {
        "flows": len(flow_results),
        "passed": sum(1 for f in flow_results if f["status"] == "PASSED"),
        "failed": sum(1 for f in flow_results if f["status"] == "FAILED"),
        "skipped": sum(1 for f in flow_results if f["status"] == "SKIPPED"),
    }

    out_dir = report_dir or (
        Path(__file__).resolve().parents[1] / "data" / "reports" / "api-test"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = default_ledger_path(out_dir)
    ledger = load_ledger(ledger_path)
    merge_flow_results_into_ledger(ledger, flow_results)
    save_ledger(ledger_path, ledger)
    hotspots = build_hotspots(ledger, flows=flow_results)

    report = {
        "generated_at": _utc(),
        "environment": environment,
        "mutations_allowed": ephemeral_on or legacy_mut,
        "feature_flags": {
            "qa-auth-ephemeral-user-flows": flag,
        },
        "ephemeral_user": {
            "enabled": ephemeral_on,
            "email": ephemeral.get("email"),
            "created": bool(ephemeral.get("email")),
            "safety_cleanup": safety_cleanup,
        },
        "decision": "GO" if counts["failed"] == 0 else "NO_GO",
        "counts": counts,
        "refresh": refresh_info,
        "flows": flow_results,
        "metrics": {
            "this_run": hotspots.get("this_run"),
            "hotspots": {
                "by_fail": hotspots.get("by_fail"),
                "by_skip": hotspots.get("by_skip"),
                "by_avg_ms": hotspots.get("by_avg_ms"),
            },
            "ledger_path": str(ledger_path),
        },
        "catalog": "ui_evidence/docs/AUTH_USER_FLOW_CATALOG.md",
    }

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    json_path = out_dir / f"auth-user-api-flows-{stamp}.json"
    html_path = out_dir / f"auth-user-api-flows-{stamp}.html"
    payload = json.dumps(report, indent=2, default=str)
    html = _render_html(report)
    json_path.write_text(payload, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    (out_dir / "auth-user-api-flows-latest.json").write_text(payload, encoding="utf-8")
    (out_dir / "auth-user-api-flows-latest.html").write_text(html, encoding="utf-8")
    report["report_json"] = str(json_path)
    report["report_html"] = str(html_path)
    return report


def _render_html(report: dict[str, Any]) -> str:
    blocks = []
    for flow in report.get("flows") or []:
        st = flow.get("status")
        color = {"PASSED": "#0a7", "FAILED": "#c33", "SKIPPED": "#888"}.get(st, "#444")
        rows = []
        for s in flow.get("steps") or []:
            sc = s.get("status")
            c2 = {
                "PASSED": "#0a7",
                "FAILED": "#c33",
                "EXPECTED": "#c80",
                "SKIPPED": "#666",
                "DISCOVERED": "#48a",
                "MISSING": "#c80",
            }.get(sc, "#444")
            rows.append(
                "<tr>"
                f"<td style='color:{c2};font-weight:600'>{sc}</td>"
                f"<td>{s.get('id')}</td>"
                f"<td>{s.get('method') or ''}</td>"
                f"<td><code>{s.get('path') or ''}</code></td>"
                f"<td>{s.get('http_status') or '—'}</td>"
                f"<td>{s.get('duration_ms') if s.get('duration_ms') is not None else '—'}</td>"
                f"<td>{s.get('reason') or s.get('note') or s.get('error') or ''}</td>"
                "</tr>"
            )
        blocks.append(
            f"<h2 style='color:{color}'>{flow.get('id')} — {flow.get('title')} "
            f"<small>({st} / {flow.get('gate')})</small></h2>"
            "<table><thead><tr><th>Status</th><th>Step</th><th>Method</th>"
            "<th>Path</th><th>Code</th><th>ms</th><th>Notes</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )
    counts = report.get("counts") or {}
    flag = (report.get("feature_flags") or {}).get("qa-auth-ephemeral-user-flows") or {}
    eph = report.get("ephemeral_user") or {}
    hotspots = (report.get("metrics") or {}).get("hotspots") or {}
    this_run = (report.get("metrics") or {}).get("this_run") or {}
    hot_html = render_hotspots_html(
        {
            "by_fail": hotspots.get("by_fail") or [],
            "by_skip": hotspots.get("by_skip") or [],
            "by_avg_ms": hotspots.get("by_avg_ms") or [],
            "this_run": this_run,
        }
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<title>Auth/User API flows — {report.get('decision')}</title>
<style>
body{{font-family:Segoe UI,system-ui,sans-serif;margin:24px;background:#0f1419;color:#e7ecf1}}
h1,h2,h3{{margin:16px 0 8px}} table{{border-collapse:collapse;width:100%;font-size:13px;margin-bottom:20px}}
th,td{{border-bottom:1px solid #2a3340;padding:8px 10px;text-align:left}}
th{{color:#9aa7b5}} code{{font-size:12px}} .meta{{color:#9aa7b5}}
.badge{{display:inline-block;padding:4px 10px;border-radius:6px;background:#1c2430;margin-right:8px}}
.hotspots{{border:1px solid #2a3340;border-radius:8px;padding:12px 16px;margin:16px 0;background:#141a22}}
</style></head><body>
<h1>Auth / User / Subscription API flows</h1>
<div class="meta">
  <span class="badge">decision: <b>{report.get('decision')}</b></span>
  <span class="badge">env: {report.get('environment')}</span>
  <span class="badge">mutations: {report.get('mutations_allowed')}</span>
  <span class="badge">generated: {report.get('generated_at')}</span>
</div>
<p class="meta">flag <code>qa-auth-ephemeral-user-flows</code> =
enabled={flag.get('enabled')} source={flag.get('source')} ·
ephemeral email={eph.get('email') or '—'}</p>
<p class="meta">flows={counts.get('flows')} · passed={counts.get('passed')} ·
failed={counts.get('failed')} · skipped={counts.get('skipped')}</p>
<p class="meta">Catalog: {report.get('catalog')}</p>
{hot_html}
{''.join(blocks)}
</body></html>
"""


def _load_optional_credential_files() -> None:
    """Merge Keycloak / GrowthBook keys from ~/.asrax without overriding set values."""
    home = Path.home() / ".asrax"
    candidates = [
        home / "credentials.env",
        home / "credentials.d" / "infra.env",
        home / "credentials.d" / "asrax.prod.env",
        home / "credentials.d" / "asrax.preprod.env",
    ]
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for path in candidates:
        if path.is_file():
            load_dotenv(path, override=False)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    from composition.env_bootstrap import load_env

    load_env()
    _load_optional_credential_files()
    load_env()  # re-apply aliases after credential merge
    report = run_auth_user_api_flows()
    print(
        json.dumps(
            {
                "decision": report["decision"],
                "counts": report["counts"],
                "feature_flags": report.get("feature_flags"),
                "ephemeral_user": {
                    "enabled": (report.get("ephemeral_user") or {}).get("enabled"),
                    "email": (report.get("ephemeral_user") or {}).get("email"),
                    "safety_cleanup": (report.get("ephemeral_user") or {}).get(
                        "safety_cleanup"
                    ),
                },
                "report_html": report["report_html"],
                "flows": [
                    {
                        "id": f["id"],
                        "status": f["status"],
                        "steps": len(f.get("steps") or []),
                    }
                    for f in report.get("flows") or []
                ],
            },
            indent=2,
        )
    )
