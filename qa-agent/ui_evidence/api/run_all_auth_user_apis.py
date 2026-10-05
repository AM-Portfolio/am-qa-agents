"""Call safe auth (identity) + user-platform APIs on prod; write HTML/JSON report."""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_IDENTITY_INCLUDE = re.compile(
    r"^/(auth|users|admin/users|admin/roles|internal/users|internal/auth|bff|health)(/|$)",
    re.I,
)

# Prod-safe: GET without path params + POST /auth/login only.
# These need cookie/BFF session or admin role — JWT login alone cannot pass them.
_SKIP_PATH_GET = (
    "/admin/",
    "/internal/",
    "/auth/device-link",
    "/bff/",
)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _tool_included(service: str, tool: dict[str, Any]) -> bool:
    path = str(tool.get("path") or "")
    if service == "am-identity":
        return bool(_IDENTITY_INCLUDE.match(path))
    if service == "am-user-platform":
        # skip catch-all and streaming
        if path in ("/{full_path}", "/mcp", "/mcp/{subpath}"):
            return False
        if "stream" in path.lower():
            return False
        return True
    if service == "am-subscription":
        # Include when OpenAPI JSON is available; HTML swagger yields 0 tools.
        if path in ("/{full_path}",):
            return False
        return True
    return False


def _skip_reason(service: str, tool: dict[str, Any]) -> str | None:
    method = str(tool.get("method") or "").lower()
    path = str(tool.get("path") or "")
    if method == "delete":
        return "DELETE skipped on prod"
    if method == "post" and service == "am-identity" and path.rstrip("/") == "/auth/login":
        return None
    if method in ("post", "put", "patch"):
        return "mutating skipped on prod"
    if method != "get":
        return f"method {method} skipped"
    if "{" in path:
        return "path params required"
    if service == "am-identity":
        for sub in _SKIP_PATH_GET:
            if path.startswith(sub) or sub in path:
                if sub == "/bff/":
                    return "BFF cookie session required (not JWT)"
                if sub == "/admin/":
                    return "admin role required — skipped for non-admin SPT user"
                return f"path skipped ({sub})"
    return None


def run_all_auth_user_apis(
    *,
    environment: str = "prod",
    services: list[str] | None = None,
    refresh: bool = True,
    report_dir: Path | None = None,
) -> dict[str, Any]:
    from specs.openapi_tools.registry import call_tool, list_tools, refresh_tools_from_prod

    services = services or ["am-identity", "am-user-platform", "am-subscription"]
    refresh_info: dict[str, Any] = {}
    if refresh:
        refresh_info = refresh_tools_from_prod(
            environment=environment, services=list(services)
        )

    user = os.environ.get("SPT_AUTH_USERNAME") or ""
    password = os.environ.get("SPT_AUTH_PASSWORD") or ""

    results: list[dict[str, Any]] = []
    tools_total = 0

    for service in services:
        listed = list_tools(service=service, limit=1000)
        tools = [t for t in (listed.get("tools") or []) if _tool_included(service, t)]
        tools.sort(key=lambda t: (str(t.get("path") or ""), str(t.get("method") or ""))
        )
        tools_total += len(tools)

        for tool in tools:
            name = str(tool.get("name") or "")
            method = str(tool.get("method") or "").lower()
            path = str(tool.get("path") or "")
            skip = _skip_reason(service, tool)
            if skip:
                results.append(
                    {
                        "service": service,
                        "tool": name,
                        "method": method.upper(),
                        "path": path,
                        "status": "SKIPPED",
                        "reason": skip,
                    }
                )
                continue
            args: dict[str, Any] = {}
            needs_auth = True
            if method == "post" and path.rstrip("/") == "/auth/login":
                if not user or not password:
                    results.append(
                        {
                            "service": service,
                            "tool": name,
                            "method": method.upper(),
                            "path": path,
                            "status": "SKIPPED",
                            "reason": "SPT_AUTH_USERNAME/PASSWORD missing",
                        }
                    )
                    continue
                args = {"username": user, "password": password}
                needs_auth = False
            elif path in ("/health", "/ready") or path.endswith("/health"):
                needs_auth = False

            out = call_tool(
                name,
                args,
                with_identity_auth=needs_auth,
                record_run=True,
            )
            http = int(out.get("status") or 0)
            ok = bool(out.get("ok"))
            body_snip = ""
            body = out.get("body")
            if isinstance(body, (dict, list)):
                body_snip = json.dumps(body, default=str)[:240]
            elif body is not None:
                body_snip = str(body)[:240]
            if ok:
                status = "PASSED"
                note = None
            elif http >= 500:
                # Real prod defect (e.g. /users/me 500 with valid JWT)
                status = "FAILED"
                note = body_snip or out.get("error") or f"HTTP {http}"
            elif http in (401, 403):
                status = "EXPECTED"
                note = body_snip or "authz gate (route live)"
            else:
                status = "FAILED"
                note = body_snip or out.get("error") or f"HTTP {http}"
            results.append(
                {
                    "service": service,
                    "tool": name,
                    "method": method.upper(),
                    "path": path,
                    "status": status,
                    "http_status": http,
                    "url": out.get("url"),
                    "error": out.get("error"),
                    "reason": note,
                    "body": body_snip or None,
                }
            )

    counts = {
        "total_tools": tools_total,
        "passed": sum(1 for r in results if r["status"] == "PASSED"),
        "failed": sum(1 for r in results if r["status"] == "FAILED"),
        "expected": sum(1 for r in results if r["status"] == "EXPECTED"),
        "skipped": sum(1 for r in results if r["status"] == "SKIPPED"),
        "called": sum(1 for r in results if r["status"] not in {"SKIPPED"}),
    }
    issues = [r for r in results if r["status"] == "FAILED"]
    decision = "GO" if not issues else "NO_GO"
    report = {
        "generated_at": _utc(),
        "environment": environment,
        "services": services,
        "scope": "am-identity auth/users + am-user-platform + am-subscription (prod Swagger)",
        "decision": decision,
        "counts": counts,
        "issues": issues,
        "refresh": refresh_info,
        "results": results,
        "legend": {
            "PASSED": "HTTP 2xx — call succeeded",
            "FAILED": "Unexpected failure (incl. 5xx with valid JWT) — real problem",
            "EXPECTED": "401/403 authz — route is live; role/session not granted",
            "SKIPPED": "Not called on prod (mutating, path-params, admin/BFF/internal)",
        },
    }

    out_dir = report_dir or (
        Path(__file__).resolve().parents[1] / "data" / "reports" / "api-test"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    json_path = out_dir / f"auth-user-apis-{stamp}.json"
    html_path = out_dir / f"auth-user-apis-{stamp}.html"
    payload = json.dumps(report, indent=2, default=str)
    html = _render_html(report)
    json_path.write_text(payload, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    (out_dir / "auth-user-apis-latest.json").write_text(payload, encoding="utf-8")
    (out_dir / "auth-user-apis-latest.html").write_text(html, encoding="utf-8")
    report["report_json"] = str(json_path)
    report["report_html"] = str(html_path)
    return report


def _rows_html(rows: list[dict[str, Any]]) -> str:
    out = []
    for r in rows:
        st = str(r.get("status") or "")
        color = {
            "PASSED": "#0a7",
            "FAILED": "#c33",
            "EXPECTED": "#c80",
            "SKIPPED": "#666",
        }.get(st, "#444")
        out.append(
            "<tr>"
            f"<td style='color:{color};font-weight:600'>{st}</td>"
            f"<td>{r.get('service')}</td>"
            f"<td>{r.get('method')}</td>"
            f"<td><code>{r.get('path')}</code></td>"
            f"<td>{r.get('http_status') or '—'}</td>"
            f"<td>{r.get('reason') or r.get('error') or ''}</td>"
            "</tr>"
        )
    return "".join(out)


def _render_html(report: dict[str, Any]) -> str:
    counts = report.get("counts") or {}
    results = list(report.get("results") or [])
    issues = [r for r in results if r.get("status") == "FAILED"]
    passed = [r for r in results if r.get("status") == "PASSED"]
    expected = [r for r in results if r.get("status") == "EXPECTED"]
    skipped = [r for r in results if r.get("status") == "SKIPPED"]
    issues_block = (
        f"<h2 style='color:#c33'>Real issues ({len(issues)})</h2>"
        "<p class='meta'>These are unexpected failures (not intentional skips).</p>"
        "<table><thead><tr><th>Status</th><th>Service</th><th>Method</th>"
        "<th>Path</th><th>Code</th><th>Notes</th></tr></thead>"
        f"<tbody>{_rows_html(issues)}</tbody></table>"
        if issues
        else "<h2 style='color:#0a7'>Real issues (0)</h2>"
        "<p class='meta'>No unexpected API failures.</p>"
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<title>Auth+User API report — {report.get('decision')}</title>
<style>
body{{font-family:Segoe UI,system-ui,sans-serif;margin:24px;background:#0f1419;color:#e7ecf1}}
h1,h2{{margin:16px 0 8px}} table{{border-collapse:collapse;width:100%;font-size:13px;margin-bottom:20px}}
th,td{{border-bottom:1px solid #2a3340;padding:8px 10px;text-align:left;vertical-align:top}}
th{{color:#9aa7b5}} code{{font-size:12px}} .meta{{color:#9aa7b5;margin-bottom:12px}}
.badge{{display:inline-block;padding:4px 10px;border-radius:6px;background:#1c2430;margin-right:8px}}
details{{margin:12px 0;color:#9aa7b5}} summary{{cursor:pointer;color:#cdd6e0}}
</style></head><body>
<h1>Auth + User API report</h1>
<div class="meta">
  <span class="badge">decision: <b>{report.get('decision')}</b></span>
  <span class="badge">env: {report.get('environment')}</span>
  <span class="badge">services: {', '.join(report.get('services') or [])}</span>
  <span class="badge">generated: {report.get('generated_at')}</span>
</div>
<p class="meta">
  <b>passed={counts.get('passed')}</b> ·
  <b style="color:#c33">failed={counts.get('failed')}</b> ·
  expected={counts.get('expected')} ·
  skipped={counts.get('skipped')} (not errors) ·
  tools={counts.get('total_tools')}
</p>
<p class="meta"><b>Legend:</b> SKIPPED = intentionally not called on prod (mutating/register/admin/BFF).
EXPECTED = 401/403 authz. FAILED = real problem.</p>
{issues_block}
<h2>Passed ({len(passed)})</h2>
<table><thead><tr><th>Status</th><th>Service</th><th>Method</th><th>Path</th><th>Code</th><th>Notes</th></tr></thead>
<tbody>{_rows_html(passed)}</tbody></table>
<details>
<summary>Expected authz ({len(expected)}) — not counted as errors</summary>
<table><thead><tr><th>Status</th><th>Service</th><th>Method</th><th>Path</th><th>Code</th><th>Notes</th></tr></thead>
<tbody>{_rows_html(expected)}</tbody></table>
</details>
<details>
<summary>Skipped on purpose ({len(skipped)}) — mutating / path-params / admin / BFF — not errors</summary>
<table><thead><tr><th>Status</th><th>Service</th><th>Method</th><th>Path</th><th>Code</th><th>Notes</th></tr></thead>
<tbody>{_rows_html(skipped)}</tbody></table>
</details>
</body></html>
"""


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    report = run_all_auth_user_apis()
    print(
        json.dumps(
            {
                "decision": report["decision"],
                "counts": report["counts"],
                "report_html": report["report_html"],
                "report_json": report["report_json"],
            },
            indent=2,
        )
    )
