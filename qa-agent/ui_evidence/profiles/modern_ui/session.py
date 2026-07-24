"""Shared login / post-login step builders for main-shell domain flows."""
from __future__ import annotations

from typing import Any

from ui_evidence.profiles.modern_ui import routes as R


def build_login_prefix(
    base_url: str,
    *,
    login_mode: str = "demo",
    email: str = "",
    password: str = "",
    open_path: str = "/",
) -> list[dict[str, Any]]:
    """Navigate to app entry and complete demo or credentials login."""
    entry = base_url.rstrip("/") + (open_path if open_path.startswith("/") else f"/{open_path}")
    if open_path == "/":
        entry = base_url.rstrip("/") + "/"

    steps: list[dict[str, Any]] = [
        {"action": "navigate", "url": entry, "name": "1. Open app"},
        {
            "action": "wait_for_login",
            "timeout_ms": 60000,
            "name": "2. Wait for Flutter login form",
        },
        {"action": "screenshot", "name": "3. Screenshot — login form"},
    ]
    if login_mode == "demo":
        steps.extend(
            [
                {"action": "click_demo_login", "name": "4. Click Demo Login"},
                {"action": "screenshot", "name": "5. Screenshot — demo login triggered"},
            ]
        )
    else:
        steps.extend(
            [
                {"action": "fill_label", "label": "Email", "text": email, "name": "4. Fill email"},
                {
                    "action": "fill_label",
                    "label": "Password",
                    "text": password,
                    "name": "5. Fill password",
                },
                {"action": "screenshot", "name": "6. Screenshot — credentials entered"},
                {
                    "action": "click_button",
                    "name_match": "Sign In",
                    "name": "7. Click Sign In",
                },
            ]
        )
    return steps


def build_post_login_wait(*, login_mode: str = "demo", expect_path: str = R.DASHBOARD) -> list[dict[str, Any]]:
    """Wait for identity redirect then assert authenticated shell URL."""
    n = 6 if login_mode == "demo" else 8
    return [
        {
            "action": "wait",
            "ms": 6000,
            "name": f"{n}. Wait for identity API + navigation",
        },
        {
            "action": "wait_for_url",
            "pattern": expect_path,
            "timeout_ms": 45000,
            "name": f"{n + 1}. Wait for URL containing {expect_path}",
        },
        {
            "action": "assert_url_contains",
            "pattern": expect_path,
            "name": f"{n + 2}. Assert URL contains {expect_path}",
        },
    ]


def build_domain_prefix(
    base_url: str,
    *,
    login_mode: str = "demo",
    email: str = "",
    password: str = "",
) -> list[dict[str, Any]]:
    """Login + land on main dashboard (used by deep-link domain smokes)."""
    return [
        *build_login_prefix(base_url, login_mode=login_mode, email=email, password=password),
        *build_post_login_wait(login_mode=login_mode, expect_path=R.DASHBOARD),
    ]


def checklist_from_steps(
    steps: list[dict[str, Any]], action_log: list[dict[str, Any]]
) -> list[dict[str, str]]:
    completed = {
        entry.get("name", "") for entry in action_log if entry.get("action") != "assert_failed"
    }
    items: list[dict[str, str]] = []
    for step in steps:
        name = step.get("name") or step.get("action", "step")
        action = step.get("action", "")
        if action.startswith("assert_"):
            failed = any(
                entry.get("action") == "assert_failed" and entry.get("step") == name
                for entry in action_log
            )
            soft_warn = any(
                entry.get("action") == "assert_soft_fail" and entry.get("step") == name
                for entry in action_log
            )
            if failed:
                status = "FAIL"
            elif soft_warn:
                status = "WARN"
            elif any(entry.get("action") == "assert_pass" for entry in action_log):
                status = "PASS"
            else:
                status = "PENDING"
        else:
            status = "PASS" if name in completed or action in ("screenshot", "wait") else "SKIP"
        items.append({"name": name, "status": status})
    return items
