"""Execute subscription-only API flows; write HTML/JSON + hotspot ledger."""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ui_evidence.api.flow_metrics import (
    build_hotspots,
    load_ledger,
    merge_flow_results_into_ledger,
    render_hotspots_html,
    save_ledger,
    subscription_ledger_path,
)
from ui_evidence.api.run_auth_user_api_flows import (
    _identity_base,
    _resolve_tool,
    _tool_meta,
)
from ui_evidence.api.subscription_api_flows import SUBSCRIPTION_API_FLOWS

logger = logging.getLogger(__name__)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_subscription_api_flows(
    *,
    environment: str = "prod",
    refresh: bool = True,
    report_dir: Path | None = None,
) -> dict[str, Any]:
    from specs.catalog.catalog_loader import _platform_openapi_headers
    from specs.openapi_tools.generator import execute_openapi_tool_sync
    from specs.openapi_tools.registry import call_tool, list_tools, refresh_tools_from_prod

    services = ["am-identity", "am-subscription"]
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

    for flow in SUBSCRIPTION_API_FLOWS:
        step_rows: list[dict[str, Any]] = []
        flow_failed = False
        for step in flow.get("steps") or []:
            t0 = time.perf_counter()

            def _add(row: dict[str, Any], _t0: float = t0) -> None:
                row["duration_ms"] = round((time.perf_counter() - _t0) * 1000, 1)
                step_rows.append(row)

            sid = str(step.get("id") or "")
            kind = str(step.get("kind") or "call_tool")
            svc = str(step.get("service") or "am-subscription")
            tools = tools_by_svc.get(svc) or []
            tool = _resolve_tool(tools, step)

            if kind != "raw_http" and not tool:
                path_hint = step.get("exact_path") or step.get("path_contains")
                if svc == "am-identity" and path_hint and step.get("method"):
                    kind = "raw_http"
                else:
                    status = "SKIPPED" if step.get("optional_service") else "FAILED"
                    _add(
                        {
                            "id": sid,
                            "status": status,
                            "reason": "no OpenAPI tool (swagger may be HTML/unavailable)",
                            "path": path_hint,
                        }
                    )
                    if status == "FAILED":
                        flow_failed = True
                    continue

            args: dict[str, Any] = {}
            if step.get("uses_spt_auth_creds"):
                args = {"username": spt_user, "password": spt_password}

            headers = {"Accept": "application/json"}
            if step.get("auth"):
                if access_token:
                    headers["Authorization"] = f"Bearer {access_token}"
                else:
                    headers.update(_platform_openapi_headers())

            method = str(
                (tool or {}).get("method") or step.get("method") or "get"
            ).lower()
            base = str(step.get("base_url_override") or identity_base).rstrip("/")
            if svc == "am-subscription" and not step.get("base_url_override"):
                # Prefer tool meta base when present
                meta_probe = _tool_meta(tool, svc=svc, step=step, base=base)
                base = str(meta_probe.get("base_url") or base).rstrip("/")
            meta = _tool_meta(tool, svc=svc, step=step, base=base)

            if kind == "raw_http" or method == "delete":
                out = execute_openapi_tool_sync(meta, args, headers=headers)
            elif access_token and step.get("auth"):
                out = execute_openapi_tool_sync(dict(meta), args, headers=headers)
            elif step.get("uses_spt_auth_creds"):
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

            if ok:
                status = "PASSED"
            elif step.get("optional_service") and not ok:
                status = "SKIPPED"
            elif 400 <= http < 500:
                status = "EXPECTED"
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
            if s.get("status") not in {"SKIPPED", "DISCOVERED", "MISSING", "EXPECTED"}
        ]
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
                "gate": flow.get("gate"),
                "status": flow_status,
                "steps": step_rows,
            }
        )

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
    ledger_path = subscription_ledger_path(out_dir)
    ledger = load_ledger(ledger_path)
    merge_flow_results_into_ledger(ledger, flow_results)
    save_ledger(ledger_path, ledger)
    hotspots = build_hotspots(ledger, flows=flow_results)

    report = {
        "generated_at": _utc(),
        "environment": environment,
        "pack": "subscription",
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
        "catalog": "ui_evidence/docs/SUBSCRIPTION_MODULE_CATALOG.md",
    }

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    json_path = out_dir / f"subscription-api-flows-{stamp}.json"
    html_path = out_dir / f"subscription-api-flows-{stamp}.html"
    html = _render_html(report)
    payload = json.dumps(report, indent=2, default=str)
    json_path.write_text(payload, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    (out_dir / "subscription-api-flows-latest.json").write_text(payload, encoding="utf-8")
    (out_dir / "subscription-api-flows-latest.html").write_text(html, encoding="utf-8")
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
            f"<small>({st})</small></h2>"
            "<table><thead><tr><th>Status</th><th>Step</th><th>Method</th>"
            "<th>Path</th><th>Code</th><th>ms</th><th>Notes</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )
    counts = report.get("counts") or {}
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
<title>Subscription API flows — {report.get('decision')}</title>
<style>
body{{font-family:Segoe UI,system-ui,sans-serif;margin:24px;background:#0f1419;color:#e7ecf1}}
h1,h2,h3{{margin:16px 0 8px}} table{{border-collapse:collapse;width:100%;font-size:13px;margin-bottom:20px}}
th,td{{border-bottom:1px solid #2a3340;padding:8px 10px;text-align:left}}
th{{color:#9aa7b5}} code{{font-size:12px}} .meta{{color:#9aa7b5}}
.badge{{display:inline-block;padding:4px 10px;border-radius:6px;background:#1c2430;margin-right:8px}}
.hotspots{{border:1px solid #2a3340;border-radius:8px;padding:12px 16px;margin:16px 0;background:#141a22}}
</style></head><body>
<h1>Subscription API flows</h1>
<div class="meta">
  <span class="badge">decision: <b>{report.get('decision')}</b></span>
  <span class="badge">env: {report.get('environment')}</span>
  <span class="badge">generated: {report.get('generated_at')}</span>
</div>
<p class="meta">flows={counts.get('flows')} · passed={counts.get('passed')} ·
failed={counts.get('failed')} · skipped={counts.get('skipped')}</p>
<p class="meta">Catalog: {report.get('catalog')}</p>
{hot_html}
{''.join(blocks)}
</body></html>
"""


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    from composition.env_bootstrap import load_env

    load_env()
    report = run_subscription_api_flows()
    print(
        json.dumps(
            {
                "decision": report["decision"],
                "counts": report["counts"],
                "report_html": report["report_html"],
            },
            indent=2,
        )
    )
