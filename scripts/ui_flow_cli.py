#!/usr/bin/env python3
"""Short UI flow dispatcher: npm run ui -- auth|portfolio|prod|list|...

Loads am-qa-agents/.env (TEST_USER_*), then runs existing ui_evidence runners.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_EVIDENCE = ROOT / "qa-agent" / "ui_evidence"
FLOW_TEST = UI_EVIDENCE / "scripts" / "run_flow_test.py"
SUITE_SCRIPT = UI_EVIDENCE / "scripts" / "run_suite.py"

# Short alias -> profile name (or suite / multi)
ALIASES: dict[str, str] = {
    "auth": "AUTH_FLOW_MAIN",
    "dashboard": "DASHBOARD_SMOKE_FLOW",
    "portfolio": "PORTFOLIO_SMOKE_FLOW",
    "portfolio-tabs": "PORTFOLIO_TABS_FLOW",
    "trade": "TRADE_SMOKE_FLOW",
    "trade-tabs": "TRADE_TABS_FLOW",
    "market": "MARKET_USER_FLOW",
    "market-gate": "MARKET_GATE_FLOW",
    "doc": "DOC_INTEL_SMOKE_FLOW",
    "profile": "PROFILE_SMOKE_FLOW",
    "subscription": "SUBSCRIPTION_SMOKE_FLOW",
    "admin-gate": "ADMIN_GATE_FLOW",
}

SUITES = {"smoke", "release_gate", "prod", "prod_ui_full"}
CORE_ALIASES = ("auth", "dashboard", "portfolio", "trade", "market")
NEEDS_PORTFOLIO = frozenset(
    {
        "portfolio",
        "portfolio-tabs",
        "trade",
        "trade-tabs",
        "core",
        "prod",
        "prod_ui_full",
        "smoke",
        "release_gate",
    }
)


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if not key:
            continue
        existing = os.environ.get(key)
        if existing is not None and str(existing).strip() != "":
            continue
        os.environ[key] = val


def _apply_defaults() -> None:
    env = (os.getenv("TEST_ENVIRONMENT") or os.getenv("APP_ENV") or "").strip().lower()
    if env == "prod":
        os.environ.setdefault("MODERN_UI_MAIN_URL", "https://am.asrax.in")
        os.environ.setdefault("AUTH_LOGIN_MODE", "credentials")
    # Keep HTML/JSON/PDF/traces under repo root so npm runs are easy to find
    os.environ.setdefault("REPORT_DIR", str(ROOT / "ui-reports"))
    # Normalize null-like portfolio ids so runners do not deep-link to "null"
    raw = (os.getenv("TEST_PORTFOLIO_ID") or "").strip()
    if raw.lower() in {"null", "none", "undefined", "-"}:
        os.environ.pop("TEST_PORTFOLIO_ID", None)
    elif raw == "":
        os.environ.pop("TEST_PORTFOLIO_ID", None)


def _report_dir() -> Path:
    return Path(os.getenv("REPORT_DIR") or (ROOT / "ui-reports"))


def _default_url() -> str:
    return (
        os.getenv("MODERN_UI_MAIN_URL")
        or ("https://am.asrax.in" if (os.getenv("TEST_ENVIRONMENT") or "").lower() == "prod" else "http://localhost:9000")
    )


def _ensure_creds() -> None:
    if not (os.getenv("TEST_USER_EMAIL") or "").strip():
        print("ERROR: TEST_USER_EMAIL missing (set in am-qa-agents/.env)", file=sys.stderr)
        raise SystemExit(2)
    if not (os.getenv("TEST_USER_PASSWORD") or "").strip():
        print("ERROR: TEST_USER_PASSWORD missing (set in am-qa-agents/.env)", file=sys.stderr)
        raise SystemExit(2)


def _portfolio_id() -> str | None:
    raw = (os.getenv("TEST_PORTFOLIO_ID") or "").strip()
    if not raw or raw.lower() in {"null", "none", "undefined", "-"}:
        return None
    return raw


def _verify_portfolio(alias: str) -> None:
    """Portfolio id is optional; when null, flows use list/legacy routes and still verify."""
    pid = _portfolio_id()
    if pid:
        print(f"TEST_PORTFOLIO_ID={pid} (deep-link verification)", flush=True)
        return
    if alias not in NEEDS_PORTFOLIO:
        print("TEST_PORTFOLIO_ID=null (not needed for this alias)", flush=True)
        return
    print(
        "TEST_PORTFOLIO_ID=null - continuing with list/legacy portfolio routes; "
        "deep-link /app/portfolio/{id}/... and /app/trade/{id}/... will not be verified. "
        "Set TEST_PORTFOLIO_ID or --portfolio-id for full coverage.",
        flush=True,
    )


def _menu_items() -> list[tuple[str, str]]:
    items = [(a, p) for a, p in ALIASES.items()]
    items.append(("core", "auth->dashboard->portfolio->trade->market"))
    items.append(("smoke", "suite smoke"))
    items.append(("prod", "suite prod_ui_full"))
    return items


def _print_list() -> None:
    print("Aliases (npm run ui -- <alias>):\n")
    for i, (alias, desc) in enumerate(_menu_items(), start=1):
        print(f"  {i:2}. {alias:<16} -> {desc}")
    print()
    print(f"REPORT_DIR={_report_dir()}")
    email = os.getenv("TEST_USER_EMAIL") or "(unset)"
    print(f"TEST_USER_EMAIL={email}")
    pid = _portfolio_id()
    print(f"TEST_PORTFOLIO_ID={pid if pid else 'null (list/legacy verification)'}")


def _interactive_pick() -> str:
    items = _menu_items()
    _print_list()
    print("\nEnter number or alias (empty = cancel): ", end="", flush=True)
    raw = sys.stdin.readline().strip()
    if not raw:
        raise SystemExit(0)
    if raw.isdigit():
        idx = int(raw)
        if 1 <= idx <= len(items):
            return items[idx - 1][0]
        print("Invalid number", file=sys.stderr)
        raise SystemExit(2)
    return raw.lower().replace("_", "-")


def _run_python(script: Path, args: list[str]) -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        str(ROOT / "qa-agent")
        + os.pathsep
        + str(ROOT / "qa-agent" / "release_gate")
        + os.pathsep
        + env.get("PYTHONPATH", "")
    )
    cmd = [sys.executable, str(script), *args]
    print(f"+ {' '.join(cmd)}", flush=True)
    print(f"REPORT_DIR={_report_dir()}", flush=True)
    return subprocess.call(cmd, cwd=str(ROOT), env=env)


def _run_profile(profile: str, *, url: str, portfolio_id: str | None, open_report: bool) -> int:
    args = [
        "--in-process",
        "--login-mode",
        "credentials",
        "--url",
        url,
        "--profile",
        profile,
    ]
    pid = (portfolio_id or "").strip() or _portfolio_id() or ""
    if pid:
        args.extend(["--portfolio-id", pid])
    if open_report:
        args.append("--open-report")
    return _run_python(FLOW_TEST, args)


def _run_suite(suite: str, *, url: str, portfolio_id: str | None) -> int:
    name = "prod_ui_full" if suite in {"prod", "prod_ui_full"} else suite
    args = ["--suite", name, "--login-mode", "credentials", "--url", url]
    pid = (portfolio_id or "").strip() or _portfolio_id() or ""
    if pid:
        args.extend(["--portfolio-id", pid])
    return _run_python(SUITE_SCRIPT, args)


def _run_core(*, url: str, portfolio_id: str | None, open_report: bool) -> int:
    code = 0
    for alias in CORE_ALIASES:
        profile = ALIASES[alias]
        print(f"\n======== core step: {alias} -> {profile} ========", flush=True)
        rc = _run_profile(profile, url=url, portfolio_id=portfolio_id, open_report=open_report)
        if rc != 0:
            code = rc
            print(f"FAILED {alias} (exit {rc}); continuing core chain", flush=True)
    return code


def main(argv: list[str] | None = None) -> int:
    _load_env_file(ROOT / ".env")
    _load_env_file(ROOT / "qa-agent" / ".env")
    _apply_defaults()

    parser = argparse.ArgumentParser(
        description="Short UI flow runner (aliases -> Playwright profiles)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  npm run ui -- list\n  npm run ui -- auth\n  npm run ui -- prod\n",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default="",
        help="alias, suite (smoke|prod), core, list, or empty for interactive",
    )
    parser.add_argument("--url", default=None, help="Override target URL")
    parser.add_argument("--portfolio-id", default=None)
    parser.add_argument("--open-report", action="store_true", help="Open HTML report when done")
    args = parser.parse_args(argv)

    target = (args.target or "").strip().lower().replace("_", "-")
    if target in {"", "pick", "menu"}:
        target = _interactive_pick()
    if target in {"list", "ls", "help", "-h", "--help"}:
        _print_list()
        return 0

    if args.portfolio_id is not None:
        cleaned = args.portfolio_id.strip()
        if cleaned.lower() in {"null", "none", "undefined", "-"} or cleaned == "":
            os.environ.pop("TEST_PORTFOLIO_ID", None)
        else:
            os.environ["TEST_PORTFOLIO_ID"] = cleaned

    _ensure_creds()
    _verify_portfolio(target)

    url = (args.url or _default_url()).rstrip("/")
    open_report = bool(args.open_report)

    if target == "core":
        return _run_core(url=url, portfolio_id=args.portfolio_id, open_report=open_report)
    if target in SUITES:
        return _run_suite(target, url=url, portfolio_id=args.portfolio_id)
    if target in ALIASES:
        return _run_profile(
            ALIASES[target],
            url=url,
            portfolio_id=args.portfolio_id,
            open_report=open_report,
        )

    # Allow raw profile names
    if target.upper().endswith("_FLOW") or target.upper().startswith("AUTH_"):
        return _run_profile(
            target.upper(),
            url=url,
            portfolio_id=args.portfolio_id,
            open_report=open_report,
        )

    print(f"Unknown target: {target!r}. Try: npm run ui -- list", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
