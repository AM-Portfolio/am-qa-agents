"""Human-readable catalog of ui-test-agent flows (works even when agent is offline)."""
from __future__ import annotations

from typing import Any

# Keep in sync with ui-test-agent PROFILE_BUILDERS / suite defaults.
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
        "summary": "Deep-link /app/portfolio overview",
        "steps": [
            "Auth prefix (login session)",
            "Deep-link portfolio overview",
            "Wait for portfolio module",
            "Screenshot overview",
        ],
        "verifications": [
            "URL matches portfolio overview",
            "Overview chrome present (soft)",
            "No error banner (soft)",
        ],
    },
    "PORTFOLIO_TABS_FLOW": {
        "label": "Portfolio sidebar tabs",
        "group": "Portfolio",
        "summary": "Sweep live sidebar: overview / holdings / heatmap / baskets",
        "steps": [
            "Auth prefix",
            "Open portfolio overview",
            "Soft-assert sidebar labels",
            "Visit holdings tab",
            "Visit heatmap tab",
            "Visit baskets tab",
            "Screenshot each surface",
        ],
        "verifications": [
            "Each tab URL/path updates",
            "Tab content mounts without hard failure",
            "No error banner across sweep (soft)",
            "Never clicks New Trade or basket creator",
        ],
    },
    "MARKET_SMOKE_FLOW": {
        "label": "Market smoke (user)",
        "group": "Market",
        "summary": "Alias of MARKET_USER_FLOW: dashboard + market-analysis",
        "steps": [
            "Auth prefix",
            "Deep-link /app/market/dashboard",
            "Deep-link /app/market/market-analysis",
            "Screenshot each",
        ],
        "verifications": [
            "Market URL/path present",
            "No error banner (soft)",
        ],
    },
    "MARKET_USER_FLOW": {
        "label": "Market user sidebar",
        "group": "Market",
        "summary": "Non-admin Market nav: dashboard + market-analysis",
        "steps": [
            "Auth prefix",
            "Deep-link market dashboard",
            "Wait for market module",
            "Deep-link market-analysis",
            "Screenshot each",
        ],
        "verifications": [
            "Dashboard and market-analysis URLs present",
            "No error banner (soft)",
        ],
    },
    "MARKET_DEV_FLOW": {
        "label": "Market developer explorers",
        "group": "Market",
        "summary": "Admin view-only: all-indices, streamer, instrument/security/etf explorers",
        "steps": [
            "Auth prefix (admin persona)",
            "Deep-link all-indices",
            "Visit streamer / instrument / security / etf explorers",
            "Screenshot each (no start/stop)",
        ],
        "verifications": [
            "Each explorer slug in URL",
            "Skips price-test, admin, developer-dashboard",
            "No mutating scheduler actions",
        ],
    },
    "MARKET_GATE_FLOW": {
        "label": "Market non-admin gate",
        "group": "Market",
        "summary": "Non-admin deep-links to admin/streamer redirect to dashboard",
        "steps": [
            "Auth prefix",
            "Deep-link /app/market/admin",
            "Assert redirect to dashboard",
            "Deep-link /app/market/streamer",
            "Assert redirect to dashboard",
        ],
        "verifications": [
            "URL contains dashboard after gated deep-links",
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
    "TRADE_TABS_FLOW": {
        "label": "Trade view tabs",
        "group": "Trade",
        "summary": "Sweep all Trade view tabs (sidebar + deep-link); never Add Trade",
        "steps": [
            "Auth prefix",
            "Open trade discovery",
            "Visit holdings / calendar / trades / journal / analysis",
            "Deep-link market-analysis / report / unified / metrics / templates",
            "Screenshot each",
        ],
        "verifications": [
            "Each tab slug in URL",
            "No error banner (soft)",
            "Never clicks Add / Edit / Delete Trade",
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
        "summary": "Document upload path (skip on prod)",
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
        "summary": "Admin-only gate check (analysis / ai-chat / lab)",
        "steps": [
            "Auth prefix",
            "Deep-link analysis and ai-chat",
            "Deep-link lab (always blocked)",
            "Screenshot gate results",
        ],
        "verifications": [
            "Non-admin redirected to dashboard",
            "Lab always redirected to dashboard",
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
    "MARKET_USER_FLOW",
    "MARKET_SMOKE_FLOW",
    "MARKET_DEV_FLOW",
    "MARKET_GATE_FLOW",
    "TRADE_SMOKE_FLOW",
    "TRADE_TABS_FLOW",
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
    "MARKET_USER_FLOW",
    "TRADE_SMOKE_FLOW",
    "DOC_INTEL_SMOKE_FLOW",
]

PROD_UI_FULL_PROFILES = [
    "AUTH_FLOW_MAIN",
    "DASHBOARD_SMOKE_FLOW",
    "PORTFOLIO_SMOKE_FLOW",
    "PORTFOLIO_TABS_FLOW",
    "TRADE_SMOKE_FLOW",
    "TRADE_TABS_FLOW",
    "MARKET_USER_FLOW",
    "MARKET_GATE_FLOW",
    "DOC_INTEL_SMOKE_FLOW",
    "PROFILE_SMOKE_FLOW",
    "SUBSCRIPTION_SMOKE_FLOW",
    "ADMIN_GATE_FLOW",
]

try:
    from ui_evidence.profiles.registry import AUTH_USER_MODULE_PROFILES as _AUTH_USER_MODULE
except Exception:  # noqa: BLE001
    _AUTH_USER_MODULE = ()

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
        "summary": "Module smoke across auth / dashboard / portfolio / market / trade / docs",
        "profiles": RELEASE_GATE_PROFILES,
    },
    {
        "id": "prod_ui_full",
        "label": "Prod UI full (read-only)",
        "summary": "Credentials login; all live Portfolio/Trade/Market sidebars; no upload or mutate",
        "profiles": PROD_UI_FULL_PROFILES,
    },
    {
        "id": "auth_user_module",
        "label": "Auth user module (Cucumber scenarios)",
        "summary": "Registration → login → forgot password → Google CTA/OAuth redirect",
        "profiles": list(_AUTH_USER_MODULE),
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
    ordered: list[str] = []
    seen: set[str] = set()
    for fid in DEFAULT_FLOW_IDS + ids:
        if fid in ids and fid not in seen:
            ordered.append(fid)
            seen.add(fid)
    flows = [_flow_entry(fid) for fid in ordered]

    rg = list(release_gate or RELEASE_GATE_PROFILES)
    suite_ids = list(
        suites or ["smoke", "release_gate", "prod_ui_full", "auth_user_module"]
    )
    suite_rows = []
    for s in SUITE_META:
        if s["id"] in suite_ids:
            suite_rows.append(dict(s))
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
        "prod_ui_full": list(PROD_UI_FULL_PROFILES),
        "default_flow": "AUTH_FLOW_MAIN",
        "default_suite": "smoke",
    }
