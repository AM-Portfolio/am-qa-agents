"""Route constants mirrored from am-modern-ui am_app/lib/core/router/app_routes.dart."""
from __future__ import annotations

from urllib.parse import urljoin

# Public auth
LOGIN = "/login"
REGISTER = "/register"
FORGOT_PASSWORD = "/forgot-password"
RESET_PASSWORD = "/reset-password"
VERIFY_EMAIL = "/verify-email"

# Authenticated shell
DASHBOARD = "/app/dashboard"
PORTFOLIO = "/app/portfolio"
TRADE = "/app/trade"
TRADE_DISCOVERY = "/app/trade/portfolios"
MARKET = "/app/market"
AI_CHAT = "/app/ai-chat"
LAB = "/app/lab"
ANALYSIS = "/app/analysis"
DOC_INTEL = "/app/doc-intel"
PROFILE = "/app/profile"
PRIVACY_POLICY = "/app/privacy-policy"
TERMS_OF_SERVICE = "/app/terms-of-service"
SUBSCRIPTION = "/app/subscription"

DOC_INTEL_TABS = ("doc-processor", "email-extractor")
PORTFOLIO_TABS = ("overview", "holdings", "analysis", "heatmap", "baskets")
TRADE_TABS = (
    "portfolios",
    "holdings",
    "calendar",
    "trades",
    "journal",
    "analysis",
    "market-analysis",
    "report",
    "unified",
    "metrics",
    "templates",
)
MARKET_STATIC_SLUGS = (
    "all-indices",
    "streamer",
    "instrument-explorer",
    "security-explorer",
    "etf-explorer",
    "price-test",
    "market-analysis",
    "admin",
    "developer-dashboard",
    "dashboard",
    "heatmap-explorer",
)

NAV_TITLE_TO_PATH = {
    "Dashboard": DASHBOARD,
    "Portfolio": "/app/portfolio/overview",
    "Trade": TRADE_DISCOVERY,
    "Market": "/app/market/dashboard",
    "AI Chat": AI_CHAT,
    "Lab": LAB,
    "Analysis": ANALYSIS,
    "Doc Intel": f"{DOC_INTEL}/doc-processor",
    "Profile": PROFILE,
    "Subscription": SUBSCRIPTION,
}

# Constants that must appear in app_routes.dart (used by check_routes_sync.py)
DART_SYNC_MARKERS = (
    "static const dashboard = '/app/dashboard';",
    "static const tradeDiscovery = '/app/trade/portfolios';",
    "static const docIntel = '/app/doc-intel';",
    "static const portfolio = '/app/portfolio';",
    "static const market = '/app/market';",
)


def app_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/") + "/"
    rel = path.lstrip("/")
    return urljoin(base, rel)


def portfolio_path(portfolio_id: str, tab: str = "overview") -> str:
    return f"/app/portfolio/{portfolio_id}/{tab}"


def portfolio_legacy_tab_path(tab: str = "overview") -> str:
    return f"/app/portfolio/{tab}"


def trade_path(portfolio_id: str, tab: str = "portfolios") -> str:
    return f"/app/trade/{portfolio_id}/{tab}"


def market_path(tab: str = "all-indices") -> str:
    return f"/app/market/{tab}"


def doc_intel_path(tab: str = "doc-processor") -> str:
    return f"{DOC_INTEL}/{tab}"
