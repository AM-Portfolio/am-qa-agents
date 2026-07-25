"""Human-readable catalog of ui-test-agent flows (works even when agent is offline)."""
from __future__ import annotations

from typing import Any

# Keep in sync with ui-test-agent PROFILE_BUILDERS / RELEASE_GATE / smoke suite defaults.
# `steps` / `verifications` are documentation for the SPT UI explorer (not executed here).
UI_FLOW_META: dict[str, dict[str, Any]] = {
    "AUTH_FLOW": {
        "label": "Login (auto mode)",
        "group": "Auth",
        "summary": "Login; main vs portfolio inferred from target URL",
        "steps": [
            "Open target URL",
            "Wait for Flutter login form",
            "Demo login or email/password Sign In",
            "Wait for identity + navigation",
        ],
        "verifications": [
            "Login form becomes visible",
            "URL lands on dashboard or portfolio overview (from URL mode)",
            "No hard error banner after login",
        ],
    },
    "AUTH_FLOW_MAIN": {
        "label": "Login → Dashboard",
        "group": "Auth",
        "summary": "Demo/credentials login then main shell dashboard",
        "steps": [
            "Navigate to main app URL",
            "Wait for Flutter login form",
            "Click Demo Login (or fill email/password + Sign In)",
            "Wait for identity API + shell navigation",
            "Screenshot post-login shell",
        ],
        "verifications": [
            "URL contains /app (main shell)",
            "Dashboard / nav chrome visible",
            "No fatal error banner",
        ],
    },
    "AUTH_FLOW_PORTFOLIO": {
        "label": "Login → Portfolio overview",
        "group": "Auth",
        "summary": "Login into portfolio shell (/portfolio/overview)",
        "steps": [
            "Navigate to portfolio entry URL",
            "Wait for Flutter login form",
            "Demo login or credentials Sign In",
            "Wait for identity + portfolio navigation",
            "Screenshot portfolio shell",
        ],
        "verifications": [
            "URL contains /portfolio/overview",
            "Overview nav label visible",
            "New Trade action visible (soft)",
        ],
    },
    "DASHBOARD_SMOKE_FLOW": {
        "label": "Dashboard smoke",
        "group": "Dashboard",
        "summary": "Open dashboard module and soft-assert shell",
        "steps": [
            "Auth prefix (login session)",
            "Deep-link /app/dashboard",
            "Wait for dashboard module",
            "Screenshot dashboard",
        ],
        "verifications": [
            "URL contains dashboard path",
            "Dashboard label visible (soft)",
            "No error banner (soft)",
        ],
    },
    "PORTFOLIO_SMOKE_FLOW": {
        "label": "Portfolio overview",
        "group": "Portfolio",
        "summary": "Deep-link /app/portfolio overview (not analysis API)",
        "steps": [
            "Auth prefix (login session)",
            "Deep-link portfolio overview",
            "Wait for portfolio module",
            "Screenshot overview",
        ],
        "verifications": [
            "URL matches portfolio overview",
            "Overview / holdings chrome present (soft)",
            "No error banner (soft)",
        ],
    },
    "PORTFOLIO_TABS_FLOW": {
        "label": "Portfolio tabs",
        "group": "Portfolio",
        "summary": "Sweep overview / holdings / analysis / heatmap / baskets",
        "steps": [
            "Auth prefix",
            "Open portfolio overview",
            "Visit holdings tab",
            "Visit analysis tab",
            "Visit heatmap tab",
            "Visit baskets tab",
            "Screenshot each surface",
        ],
        "verifications": [
            "Each tab URL/path updates",
            "Tab content mounts without hard failure",
            "No error banner across sweep (soft)",
        ],
    },
    "MARKET_SMOKE_FLOW": {
        "label": "Market smoke",
        "group": "Market",
        "summary": "Open market module",
        "steps": [
            "Auth prefix",
            "Deep-link market module",
            "Wait for market shell",
            "Screenshot market",
        ],
        "verifications": [
            "Market URL/path present",
            "Market chrome visible (soft)",
            "No error banner (soft)",
        ],
    },
    "TRADE_SMOKE_FLOW": {
        "label": "Trade discovery",
        "group": "Trade",
        "summary": "Deep-link trade portfolios discovery",
        "steps": [
            "Auth prefix",
            "Deep-link trade discovery",
            "Wait for trade module",
            "Screenshot trade",
        ],
        "verifications": [
            "Trade discovery URL present",
            "Trade list/shell visible (soft)",
            "No error banner (soft)",
        ],
    },
    "DOC_INTEL_SMOKE_FLOW": {
        "label": "Doc intelligence",
        "group": "Docs",
        "summary": "Open document intelligence module",
        "steps": [
            "Auth prefix",
            "Deep-link doc intelligence",
            "Wait for docs module",
            "Screenshot docs home",
        ],
        "verifications": [
            "Docs module URL present",
            "Docs shell visible (soft)",
            "No error banner (soft)",
        ],
    },
    "DOC_UPLOAD_FLOW": {
        "label": "Doc upload",
        "group": "Docs",
        "summary": "Document upload path",
        "steps": [
            "Doc intelligence smoke prefix",
            "Open upload control",
            "Select / attach sample document (when configured)",
            "Screenshot upload state",
        ],
        "verifications": [
            "Upload control reachable",
            "Upload interaction does not crash shell",
            "Feedback or progress visible (soft)",
        ],
    },
    "PROFILE_SMOKE_FLOW": {
        "label": "User profile",
        "group": "Account",
        "summary": "Open user profile settings",
        "steps": [
            "Auth prefix",
            "Deep-link user profile",
            "Wait for profile module",
            "Screenshot profile",
        ],
        "verifications": [
            "Profile URL/path present",
            "Profile fields/shell visible (soft)",
            "No error banner (soft)",
        ],
    },
    "SUBSCRIPTION_SMOKE_FLOW": {
        "label": "Subscription",
        "group": "Account",
        "summary": "Subscription / billing surface",
        "steps": [
            "Auth prefix",
            "Deep-link subscription / billing",
            "Wait for subscription module",
            "Screenshot subscription",
        ],
        "verifications": [
            "Subscription URL present",
            "Billing surface mounts (soft)",
            "No error banner (soft)",
        ],
    },
    "ADMIN_GATE_FLOW": {
        "label": "Admin gate",
        "group": "Account",
        "summary": "Admin-only gate check",
        "steps": [
            "Auth prefix",
            "Deep-link admin gate route",
            "Observe allow or deny UI",
            "Screenshot gate result",
        ],
        "verifications": [
            "Gate route resolves (allow or blocked)",
            "Expected admin affordance when role allows",
            "No unexpected crash banner",
        ],
    },
}

DEFAULT_FLOW_IDS = [
    "AUTH_FLOW_MAIN",
    "AUTH_FLOW_PORTFOLIO",
    "DASHBOARD_SMOKE_FLOW",
    "PORTFOLIO_SMOKE_FLOW",
    "PORTFOLIO_TABS_FLOW",
    "MARKET_SMOKE_FLOW",
    "TRADE_SMOKE_FLOW",
    "DOC_INTEL_SMOKE_FLOW",
    "DOC_UPLOAD_FLOW",
    "PROFILE_SMOKE_FLOW",
    "SUBSCRIPTION_SMOKE_FLOW",
    "ADMIN_GATE_FLOW",
]

SMOKE_SUITE_PROFILES = [
    "AUTH_FLOW_MAIN",
    "DASHBOARD_SMOKE_FLOW",
    "PORTFOLIO_SMOKE_FLOW",
]

RELEASE_GATE_PROFILES = [
    "AUTH_FLOW_MAIN",
    "DASHBOARD_SMOKE_FLOW",
    "PORTFOLIO_SMOKE_FLOW",
    "MARKET_SMOKE_FLOW",
    "TRADE_SMOKE_FLOW",
    "DOC_INTEL_SMOKE_FLOW",
]

SUITE_META = [
    {
        "id": "smoke",
        "label": "Smoke suite",
        "summary": "Quick gate: auth + dashboard + portfolio",
        "profiles": SMOKE_SUITE_PROFILES,
    },
    {
        "id": "release_gate",
        "label": "Release gate",
        "summary": "Full release checklist across main modules",
        "profiles": RELEASE_GATE_PROFILES,
    },
]


def _flow_entry(flow_id: str) -> dict[str, Any]:
    meta = UI_FLOW_META.get(flow_id) or {}
    return {
        "id": flow_id,
        "label": meta.get("label") or flow_id.replace("_", " ").title(),
        "group": meta.get("group") or "Other",
        "summary": meta.get("summary") or "",
        "steps": list(meta.get("steps") or []),
        "verifications": list(meta.get("verifications") or []),
    }


def build_ui_flow_catalog(
    *,
    deterministic: list[str] | None = None,
    release_gate: list[str] | None = None,
    suites: list[str] | None = None,
    agent_online: bool = False,
    agent_url: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    ids = list(deterministic or DEFAULT_FLOW_IDS)
    # Prefer known order; append unknowns from agent
    ordered: list[str] = []
    seen: set[str] = set()
    for fid in DEFAULT_FLOW_IDS + ids:
        if fid in ids and fid not in seen:
            ordered.append(fid)
            seen.add(fid)
    flows = [_flow_entry(fid) for fid in ordered]

    rg = list(release_gate or RELEASE_GATE_PROFILES)
    suite_ids = list(suites or ["smoke", "release_gate"])
    suite_rows = []
    for s in SUITE_META:
        if s["id"] in suite_ids:
            suite_rows.append(dict(s))
    # If agent sent release_gate list, reflect it on that suite
    for row in suite_rows:
        if row["id"] == "release_gate" and rg:
            row["profiles"] = rg

    return {
        "agent": {
            "online": agent_online,
            "url": agent_url,
            "error": error,
        },
        "flows": flows,
        "suites": suite_rows,
        "deterministic": ordered,
        "release_gate": rg,
        "default_flow": "AUTH_FLOW_MAIN",
        "default_suite": "smoke",
    }
