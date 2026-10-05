#!/usr/bin/env python3
"""Run complete auth + users + subscription pack (UI + API) → one HTML report.

Usage (from qa-agent):
  set PYTHONPATH=.
  python -u ui_evidence/scripts/run_auth_module_complete.py
  python -u ui_evidence/scripts/run_auth_module_complete.py --skip-ui
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

UI_ROOT = Path(__file__).resolve().parents[1]  # ui_evidence/
QA_ROOT = Path(__file__).resolve().parents[2]  # qa-agent/
for p in (QA_ROOT, UI_ROOT, QA_ROOT.parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_env() -> None:
    from composition.env_bootstrap import load_env

    load_env()
    home = Path.home() / ".asrax"
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for path in (
        home / "credentials.env",
        home / "credentials.d" / "infra.env",
        home / "credentials.d" / "asrax.prod.env",
        home / "credentials.d" / "asrax.preprod.env",
    ):
        if path.is_file():
            load_dotenv(path, override=False)
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
        link_html = f"<a href='file:///{link.replace(chr(92), '/')}'>report</a>" if link else "—"
        ui_rows.append(
            "<tr>"
            f"<td style='color:{c};font-weight:600'>{st}</td>"
            f"<td>{r.get('profile')}</td>"
            f"<td>{r.get('duration_ms') if r.get('duration_ms') is not None else '—'}</td>"
            f"<td>{r.get('soft_failures') or 0}</td>"
            f"<td>{link_html}</td>"
            f"<td>{r.get('error') or ''}</td>"
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
            f"<td>{f.get('gate')}</td>"
            "</tr>"
        )

    sweep_c = api_sweep.get("counts") or {}
    flag = (api_flows.get("feature_flags") or {}).get("qa-auth-ephemeral-user-flows") or {}
    eph = api_flows.get("ephemeral_user") or {}
    hot_html = render_hotspots_html(
        {
            "by_fail": hotspots.get("by_fail") or [],
            "by_skip": hotspots.get("by_skip") or [],
            "by_avg_ms": hotspots.get("by_avg_ms") or [],
            "this_run": this_run,
        }
    )

    ui_hot = sorted(
        [
            {
                "profile": r.get("profile"),
                "status": r.get("status"),
                "duration_ms": r.get("duration_ms") or 0,
                "failed": 1 if r.get("status") == "FAILED" else 0,
            }
            for r in (ui.get("results") or [])
        ],
        key=lambda x: (x["failed"], float(x["duration_ms"] or 0)),
        reverse=True,
    )[:10]
    ui_hot_rows = "".join(
        "<tr>"
        f"<td>{r['profile']}</td><td>{r['status']}</td><td>{r['duration_ms']}</td>"
        "</tr>"
        for r in ui_hot
    )

    api_flow_html = api_flows.get("report_html") or ""
    api_sweep_html = api_sweep.get("report_html") or ""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<title>Auth module complete — {report.get('decision')}</title>
<style>
body{{font-family:Segoe UI,system-ui,sans-serif;margin:24px;background:#0f1419;color:#e7ecf1}}
h1,h2,h3{{margin:16px 0 8px}} table{{border-collapse:collapse;width:100%;font-size:13px;margin-bottom:20px}}
th,td{{border-bottom:1px solid #2a3340;padding:8px 10px;text-align:left}}
th{{color:#9aa7b5}} code{{font-size:12px}} .meta{{color:#9aa7b5}}
.badge{{display:inline-block;padding:4px 10px;border-radius:6px;background:#1c2430;margin-right:8px}}
.hotspots{{border:1px solid #2a3340;border-radius:8px;padding:12px 16px;margin:16px 0;background:#141a22}}
a{{color:#6cb6ff}}
section{{margin:24px 0}}
</style></head><body>
<h1>Complete auth + users + subscription</h1>
<div class="meta">
  <span class="badge">decision: <b>{report.get('decision')}</b></span>
  <span class="badge">env: {report.get('environment')}</span>
  <span class="badge">generated: {report.get('generated_at')}</span>
</div>
<p class="meta">UI suite=<code>{ui.get('suite')}</code> decision={ui.get('decision')}
hard_fail={ui.get('hard_fail_count')} soft_fail={ui.get('soft_fail_count')}</p>
<p class="meta">API flows decision={api_flows.get('decision')} ·
API sweep decision={api_sweep.get('decision')}
(passed={sweep_c.get('passed')} failed={sweep_c.get('failed')}
expected={sweep_c.get('expected')} skipped={sweep_c.get('skipped')})</p>
<p class="meta">flag <code>qa-auth-ephemeral-user-flows</code> =
enabled={flag.get('enabled')} source={flag.get('source')} ·
ephemeral={eph.get('email') or '—'}</p>
{hot_html}
<section>
<h2>UI profiles (slowest / fails first)</h2>
<table><thead><tr><th>Profile</th><th>Status</th><th>ms</th></tr></thead>
<tbody>{ui_hot_rows or '<tr><td colspan=3>—</td></tr>'}</tbody></table>
<h3>All UI results</h3>
<table><thead><tr><th>Status</th><th>Profile</th><th>ms</th><th>Soft</th><th>Report</th><th>Error</th></tr></thead>
<tbody>{''.join(ui_rows) or '<tr><td colspan=6>no UI results</td></tr>'}</tbody></table>
<p class="meta">Suite summary: <code>{ui.get('report_json') or '—'}</code></p>
</section>
<section>
<h2>API flows</h2>
<table><thead><tr><th>Status</th><th>Id</th><th>Title</th><th>Steps</th><th>Gate</th></tr></thead>
<tbody>{''.join(flow_rows) or '<tr><td colspan=5>—</td></tr>'}</tbody></table>
<p class="meta">Detail HTML: <a href="file:///{api_flow_html.replace(chr(92), '/')}">{api_flow_html or '—'}</a></p>
</section>
<section>
<h2>API users / subscription sweep</h2>
<p class="meta">passed={sweep_c.get('passed')} · failed={sweep_c.get('failed')} ·
expected={sweep_c.get('expected')} · skipped={sweep_c.get('skipped')}</p>
<p class="meta">Detail HTML: <a href="file:///{api_sweep_html.replace(chr(92), '/')}">{api_sweep_html or '—'}</a></p>
</section>
</body></html>
"""


async def _run_ui(args: argparse.Namespace) -> dict[str, Any]:
    from ui_evidence.scripts.run_suite import main_async

    ns = SimpleNamespace(
        suite="auth_users_subs_module",
        url=args.url,
        target_file=args.target_file,
        target=args.target,
        env_file=args.env_file,
        portfolio_id=args.portfolio_id,
        login_mode="credentials",
        design_review=bool(args.design_review),
        tracking_id=None,
        workflow_id=None,
        release_id=None,
        env=args.environment,
        requested_by="auth-module-complete",
    )
    code, summary = await main_async(ns)
    summary = dict(summary or {})
    summary["exit_code"] = code
    return summary


def _run_api_flows(environment: str) -> dict[str, Any]:
    from ui_evidence.api.run_auth_user_api_flows import run_auth_user_api_flows

    return run_auth_user_api_flows(
        environment=environment,
        refresh=True,
        report_dir=_api_report_dir(),
    )


def _run_api_sweep(environment: str) -> dict[str, Any]:
    from ui_evidence.api.flow_metrics import (
        default_ledger_path,
        load_ledger,
        merge_sweep_into_ledger,
        save_ledger,
    )
    from ui_evidence.api.run_all_auth_user_apis import run_all_auth_user_apis

    report = run_all_auth_user_apis(
        environment=environment,
        services=["am-identity", "am-user-platform", "am-subscription"],
        refresh=True,
        report_dir=_api_report_dir(),
    )
    ledger_path = default_ledger_path(_api_report_dir())
    ledger = load_ledger(ledger_path)
    merge_sweep_into_ledger(ledger, list(report.get("results") or []))
    save_ledger(ledger_path, ledger)
    return report


def build_combined_report(
    *,
    ui: dict[str, Any],
    api_flows: dict[str, Any],
    api_sweep: dict[str, Any],
    environment: str,
) -> dict[str, Any]:
    ui_hard = int(ui.get("hard_fail_count") or 0)
    api_failed = int((api_flows.get("counts") or {}).get("failed") or 0)
    sweep_failed = int((api_sweep.get("counts") or {}).get("failed") or 0)
    # Plan: sweep expected/skipped do not NO_GO; real FAILED does
    decision = "GO" if ui_hard == 0 and api_failed == 0 and sweep_failed == 0 else "NO_GO"
    metrics = api_flows.get("metrics") or {}
    return {
        "generated_at": _utc(),
        "environment": environment,
        "decision": decision,
        "ui": ui,
        "api_flows": {
            "decision": api_flows.get("decision"),
            "counts": api_flows.get("counts"),
            "flows": api_flows.get("flows"),
            "feature_flags": api_flows.get("feature_flags"),
            "ephemeral_user": api_flows.get("ephemeral_user"),
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
        "metrics": metrics,
    }


async def run_complete(args: argparse.Namespace) -> dict[str, Any]:
    _load_env()
    environment = args.environment

    # API first (flows → sweep), then optional UI
    print("=== API auth_user_api_flows ===", flush=True)
    api_flows = _run_api_flows(environment)

    print("=== API run_all_auth_user_apis (users + subscription) ===", flush=True)
    api_sweep = _run_api_sweep(environment)

    if args.skip_ui:
        ui: dict[str, Any] = {
            "suite": "auth_users_subs_module",
            "decision": "SKIPPED",
            "hard_fail_count": 0,
            "soft_fail_count": 0,
            "results": [],
        }
        print("=== UI skipped (--skip-ui); run again without flag after API verify ===", flush=True)
    else:
        print("=== UI auth_users_subs_module ===", flush=True)
        ui = await _run_ui(args)

    report = build_combined_report(
        ui=ui,
        api_flows=api_flows,
        api_sweep=api_sweep,
        environment=environment,
    )

    out_dir = _api_report_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    json_path = out_dir / f"auth-module-complete-{stamp}.json"
    html_path = out_dir / f"auth-module-complete-{stamp}.html"
    payload = json.dumps(report, indent=2, default=str)
    html = _render_combined(report)
    json_path.write_text(payload, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    (out_dir / "auth-module-complete-latest.json").write_text(payload, encoding="utf-8")
    (out_dir / "auth-module-complete-latest.html").write_text(html, encoding="utf-8")
    report["report_json"] = str(json_path)
    report["report_html"] = str(html_path)
    return report


def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser(
        description="Complete auth + users + subscription (UI + API) report"
    )
    parser.add_argument("--environment", default="prod")
    parser.add_argument("--url", default=None, help="Modern UI base URL")
    parser.add_argument("--target-file", default=None)
    parser.add_argument("--target", default=None)
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--portfolio-id", default=None)
    parser.add_argument("--design-review", action="store_true")
    parser.add_argument("--skip-ui", action="store_true", help="API legs only")
    parser.add_argument("--open-report", action="store_true")
    args = parser.parse_args()

    report = asyncio.run(run_complete(args))
    print(
        json.dumps(
            {
                "decision": report["decision"],
                "report_html": report["report_html"],
                "report_json": report["report_json"],
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
