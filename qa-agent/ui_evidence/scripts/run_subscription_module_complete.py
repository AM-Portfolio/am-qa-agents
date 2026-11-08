#!/usr/bin/env python3
"""Subscription-only pack: API first, then UI suite → combined report.

Usage (from qa-agent):
  set PYTHONPATH=.
  python -u ui_evidence/scripts/run_subscription_module_complete.py
  python -u ui_evidence/scripts/run_subscription_module_complete.py --skip-ui
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

UI_ROOT = Path(__file__).resolve().parents[1]
QA_ROOT = Path(__file__).resolve().parents[2]
for p in (QA_ROOT, UI_ROOT, QA_ROOT.parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_env() -> None:
    from composition.env_bootstrap import load_env

    load_env()


def _api_report_dir() -> Path:
    return UI_ROOT / "data" / "reports" / "api-test"


def _render_combined(report: dict[str, Any]) -> str:
    from ui_evidence.api.flow_metrics import render_hotspots_html

    ui = report.get("ui") or {}
    api_flows = report.get("api_flows") or {}
    api_sweep = report.get("api_sweep") or {}
    metrics = report.get("metrics") or {}
    hotspots = metrics.get("hotspots") or {}
    this_run = metrics.get("this_run") or {}

    ui_rows = []
    for r in ui.get("results") or []:
        st = r.get("status")
        c = {"PASSED": "#0a7", "FAILED": "#c33", "COMPLETED": "#0a7"}.get(st, "#888")
        link = r.get("report") or ""
        link_html = (
            f"<a href='file:///{link.replace(chr(92), '/')}'>report</a>" if link else "—"
        )
        ui_rows.append(
            "<tr>"
            f"<td style='color:{c};font-weight:600'>{st}</td>"
            f"<td>{r.get('profile')}</td>"
            f"<td>{r.get('duration_ms') if r.get('duration_ms') is not None else '—'}</td>"
            f"<td>{link_html}</td>"
            "</tr>"
        )

    flow_rows = []
    for f in api_flows.get("flows") or []:
        st = f.get("status")
        c = {"PASSED": "#0a7", "FAILED": "#c33", "SKIPPED": "#888"}.get(st, "#444")
        flow_rows.append(
            "<tr>"
            f"<td style='color:{c};font-weight:600'>{st}</td>"
            f"<td>{f.get('id')}</td>"
            f"<td>{f.get('title')}</td>"
            f"<td>{len(f.get('steps') or [])}</td>"
            "</tr>"
        )

    sweep_c = api_sweep.get("counts") or {}
    hot_html = render_hotspots_html(
        {
            "by_fail": hotspots.get("by_fail") or [],
            "by_skip": hotspots.get("by_skip") or [],
            "by_avg_ms": hotspots.get("by_avg_ms") or [],
            "this_run": this_run,
        }
    )
    api_flow_html = str(api_flows.get("report_html") or "").replace("\\", "/")
    api_sweep_html = str(api_sweep.get("report_html") or "").replace("\\", "/")

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<title>Subscription module — {report.get('decision')}</title>
<style>
body{{font-family:Segoe UI,system-ui,sans-serif;margin:24px;background:#0f1419;color:#e7ecf1}}
h1,h2,h3{{margin:16px 0 8px}} table{{border-collapse:collapse;width:100%;font-size:13px;margin-bottom:20px}}
th,td{{border-bottom:1px solid #2a3340;padding:8px 10px;text-align:left}}
th{{color:#9aa7b5}} code{{font-size:12px}} .meta{{color:#9aa7b5}}
.badge{{display:inline-block;padding:4px 10px;border-radius:6px;background:#1c2430;margin-right:8px}}
.hotspots{{border:1px solid #2a3340;border-radius:8px;padding:12px 16px;margin:16px 0;background:#141a22}}
a{{color:#6cb6ff}}
</style></head><body>
<h1>Subscription module (API + UI)</h1>
<div class="meta">
  <span class="badge">decision: <b>{report.get('decision')}</b></span>
  <span class="badge">env: {report.get('environment')}</span>
  <span class="badge">generated: {report.get('generated_at')}</span>
</div>
<p class="meta">UI suite=<code>{ui.get('suite')}</code> decision={ui.get('decision')}
hard_fail={ui.get('hard_fail_count')}</p>
<p class="meta">API flows={api_flows.get('decision')} · sweep={api_sweep.get('decision')}
(passed={sweep_c.get('passed')} failed={sweep_c.get('failed')}
skipped={sweep_c.get('skipped')})</p>
<p class="meta">Catalog: ui_evidence/docs/SUBSCRIPTION_MODULE_CATALOG.md</p>
{hot_html}
<section>
<h2>UI profiles</h2>
<table><thead><tr><th>Status</th><th>Profile</th><th>ms</th><th>Report</th></tr></thead>
<tbody>{''.join(ui_rows) or '<tr><td colspan=4>—</td></tr>'}</tbody></table>
</section>
<section>
<h2>API flows</h2>
<table><thead><tr><th>Status</th><th>Id</th><th>Title</th><th>Steps</th></tr></thead>
<tbody>{''.join(flow_rows) or '<tr><td colspan=4>—</td></tr>'}</tbody></table>
<p class="meta"><a href="file:///{api_flow_html}">{api_flow_html or '—'}</a></p>
</section>
<section>
<h2>API subscription sweep</h2>
<p class="meta">passed={sweep_c.get('passed')} failed={sweep_c.get('failed')}
skipped={sweep_c.get('skipped')}</p>
<p class="meta"><a href="file:///{api_sweep_html}">{api_sweep_html or '—'}</a></p>
</section>
</body></html>
"""


async def _run_ui(args: argparse.Namespace) -> dict[str, Any]:
    from ui_evidence.scripts.run_suite import main_async

    ns = SimpleNamespace(
        suite="subscription_module",
        url=args.url,
        target_file=args.target_file,
        target=args.target,
        env_file=args.env_file,
        portfolio_id=args.portfolio_id,
        login_mode="credentials",
        design_review=False,
        tracking_id=getattr(args, "tracking_id", None),
        workflow_id=getattr(args, "workflow_id", None),
        release_id=getattr(args, "release_id", None),
        env=args.environment,
        requested_by=getattr(args, "requested_by", None) or "subscription-module",
    )
    code, summary = await main_async(ns)
    summary = dict(summary or {})
    summary["exit_code"] = code
    return summary


def _run_api(environment: str) -> dict[str, Any]:
    """Plugin pack runner: select/prep/execute (fail-closed on env=dev)."""
    from ui_evidence.plugins.pack_runner import run_api_pack

    return run_api_pack("subscription", environment)


def build_combined_report(
    *,
    ui: dict[str, Any],
    api_pack_result: dict[str, Any],
    environment: str,
) -> dict[str, Any]:
    api_flows = api_pack_result.get("api_flows") or {}
    api_sweep = api_pack_result.get("api_sweep") or {}
    ui_hard = int(ui.get("hard_fail_count") or 0)
    api_failed = int((api_flows.get("counts") or {}).get("failed") or 0)
    sweep_failed = int((api_sweep.get("counts") or {}).get("failed") or 0)
    pack_decision = str(api_pack_result.get("decision") or "NO_GO")
    if pack_decision != "GO":
        decision = "NO_GO"
    else:
        decision = (
            "GO" if ui_hard == 0 and api_failed == 0 and sweep_failed == 0 else "NO_GO"
        )
    return {
        "generated_at": _utc(),
        "environment": environment,
        "pack": "subscription_module",
        "decision": decision,
        "llm_invoked": bool(api_pack_result.get("llm_invoked")),
        "prep": api_pack_result.get("prep") or {},
        "bank": api_pack_result.get("bank") or {},
        "ui": ui,
        "api_flows": {
            "decision": api_flows.get("decision"),
            "counts": api_flows.get("counts"),
            "flows": api_flows.get("flows"),
            "report_html": api_flows.get("report_html"),
            "report_json": api_flows.get("report_json"),
        },
        "api_sweep": {
            "decision": api_sweep.get("decision"),
            "counts": api_sweep.get("counts"),
            "report_html": api_sweep.get("report_html"),
            "report_json": api_sweep.get("report_json"),
            "issues": api_sweep.get("issues"),
        },
        "metrics": api_flows.get("metrics") or {},
        "catalog": "ui_evidence/docs/SUBSCRIPTION_MODULE_CATALOG.md",
        "executed": bool(api_pack_result.get("executed")),
        "pack_reason": api_pack_result.get("reason"),
    }


async def run_complete(args: argparse.Namespace) -> dict[str, Any]:
    _load_env()
    environment = args.environment

    print("=== API pack (plugin + bank select/prep) ===", flush=True)
    api_pack_result = _run_api(environment)
    print(
        f"=== API pack decision={api_pack_result.get('decision')} "
        f"executed={api_pack_result.get('executed')} ===",
        flush=True,
    )

    if args.skip_ui:
        ui: dict[str, Any] = {
            "suite": "subscription_module",
            "decision": "SKIPPED",
            "hard_fail_count": 0,
            "soft_fail_count": 0,
            "results": [],
        }
        print("=== UI skipped (--skip-ui) ===", flush=True)
    else:
        if not api_pack_result.get("executed") and api_pack_result.get("decision") == "NO_GO":
            ui = {
                "suite": "subscription_module",
                "decision": "SKIPPED",
                "hard_fail_count": 0,
                "soft_fail_count": 0,
                "results": [],
                "reason": "api_prep_fail_closed",
            }
            print("=== UI skipped (prep fail-closed) ===", flush=True)
        else:
            print("=== UI subscription_module ===", flush=True)
            ui = await _run_ui(args)

    report = build_combined_report(
        ui=ui,
        api_pack_result=api_pack_result,
        environment=environment,
    )
    out_dir = _api_report_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    json_path = out_dir / f"subscription-module-complete-{stamp}.json"
    html_path = out_dir / f"subscription-module-complete-{stamp}.html"
    payload = json.dumps(report, indent=2, default=str)
    html = _render_combined(report)
    json_path.write_text(payload, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    (out_dir / "subscription-module-complete-latest.json").write_text(
        payload, encoding="utf-8"
    )
    (out_dir / "subscription-module-complete-latest.html").write_text(
        html, encoding="utf-8"
    )
    report["report_json"] = str(json_path)
    report["report_html"] = str(html_path)
    return report


def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser(description="Subscription module API+UI complete")
    parser.add_argument("--environment", default="dev")
    parser.add_argument("--url", default=None)
    parser.add_argument("--target-file", default=None)
    parser.add_argument("--target", default=None)
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--portfolio-id", default=None)
    parser.add_argument("--skip-ui", action="store_true")
    parser.add_argument("--open-report", action="store_true")
    parser.add_argument("--tracking-id", default=None)
    parser.add_argument("--workflow-id", default=None)
    parser.add_argument("--release-id", default=None)
    parser.add_argument("--requested-by", default=None)
    args = parser.parse_args()
    report = asyncio.run(run_complete(args))
    print(
        json.dumps(
            {
                "decision": report["decision"],
                "report_html": report["report_html"],
                "ui_decision": (report.get("ui") or {}).get("decision"),
                "api_flows_decision": (report.get("api_flows") or {}).get("decision"),
                "api_sweep_decision": (report.get("api_sweep") or {}).get("decision"),
            },
            indent=2,
        )
    )
    if args.open_report:
        webbrowser.open(Path(report["report_html"]).as_uri())
    return 0 if report.get("decision") == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
