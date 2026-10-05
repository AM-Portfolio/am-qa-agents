"""Deterministic builders for auth Feature Scenarios (Cucumber-style suite)."""
from __future__ import annotations

import time
from typing import Any

from ui_evidence.profiles.modern_ui import routes as R
from ui_evidence.profiles.modern_ui.auth_flow import (
    _login_steps,
    _main_app_auth_steps,
    auth_verification_checklist,
)
from ui_evidence.profiles.modern_ui.session import checklist_from_steps


def _app_url(base_url: str, path: str) -> str:
    return R.app_url(base_url, path)


def _open_public(base_url: str, path: str, *, title: str) -> list[dict[str, Any]]:
    return [
        {
            "action": "navigate",
            "url": _app_url(base_url, path),
            "name": f"1. Open {title}",
        },
        {
            "action": "wait_for_flutter",
            "timeout_ms": 60000,
            "name": "2. Wait for Flutter web bootstrap",
        },
        {"action": "wait", "ms": 2000, "name": "2b. Settle Flutter semantics"},
        {"action": "screenshot", "name": f"3. Screenshot — {title}"},
    ]


def build_auth_reg_open_steps(
    *,
    target_url: str,
    email: str = "",
    password: str = "",
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    return [
        *_open_public(target_url, R.REGISTER, title="register page"),
        {
            "action": "assert_url_contains",
            "pattern": R.REGISTER,
            "name": "4. Assert URL contains /register",
        },
        {
            "action": "assert_text_visible",
            "texts": [
                "Create your account",
                "Create Account",
                "Join",
                "Register",
                "Full name",
                "Email address",
            ],
            "soft": True,
            "name": "5. Soft assert register form copy",
        },
    ]


def build_auth_reg_validation_steps(
    *,
    target_url: str,
    email: str = "",
    password: str = "",
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    return [
        *_open_public(target_url, R.REGISTER, title="register page"),
        {
            "action": "click_button",
            "name_match": "Create Account",
            "name": "4. Click Create Account empty",
        },
        {"action": "wait", "ms": 1500, "name": "5. Wait for validation"},
        {
            "action": "assert_text_visible",
            "texts": ["Please enter your full name", "full name", "required"],
            "soft": True,
            "name": "6. Assert validation feedback",
        },
        {
            "action": "assert_url_contains",
            "pattern": R.REGISTER,
            "name": "7. Assert still on /register",
        },
        {"action": "screenshot", "name": "8. Screenshot — validation"},
    ]


def build_auth_reg_fill_steps(
    *,
    target_url: str,
    email: str = "",
    password: str = "",
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    stamp = int(time.time())
    unique_email = f"qa+reg{stamp}@asrax.test"
    fill_password = password or "QaTest!23456"
    return [
        *_open_public(target_url, R.REGISTER, title="register page"),
        {
            "action": "fill_label",
            "label": "Full name",
            "text": f"QA Reg {stamp}",
            "name": "4. Fill Full name",
        },
        {
            "action": "fill_label",
            "label": "Email address",
            "text": unique_email,
            "name": "5. Fill Email address",
        },
        {
            "action": "fill_label",
            "label": "Password",
            "text": fill_password,
            "name": "6. Fill Password",
        },
        {
            "action": "fill_label",
            "label": "Confirm password",
            "text": fill_password,
            "name": "7. Fill Confirm password",
        },
        {"action": "screenshot", "name": "8. Screenshot — form filled (no submit)"},
        {
            "action": "assert_text_visible",
            "texts": ["Create Account"],
            "name": "9. Assert Create Account still available",
        },
        {
            "action": "assert_url_contains",
            "pattern": R.REGISTER,
            "name": "10. Assert still on /register (did not submit)",
        },
    ]


def build_auth_login_ok_steps(
    *,
    target_url: str,
    email: str,
    password: str,
    login_mode: str = "credentials",
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    mode = "credentials" if login_mode == "demo" else login_mode
    return _main_app_auth_steps(target_url, email, password, mode)


def build_auth_login_bad_pw_steps(
    *,
    target_url: str,
    email: str,
    password: str = "",
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    bad = (password or "x") + "__wrong__"
    entry = target_url.rstrip("/") + "/"
    return [
        {"action": "navigate", "url": entry, "name": "1. Open main AM app home"},
        *_login_steps("credentials", email, bad),
        {"action": "wait", "ms": 4000, "name": "8. Wait for auth error"},
        {
            "action": "assert_text_visible",
            "texts": [
                "Invalid",
                "incorrect",
                "failed",
                "wrong",
                "Unable",
                "error",
                "credentials",
            ],
            "soft": True,
            "name": "9. Assert auth error message",
        },
        {
            "action": "assert_url_contains",
            "pattern": "/login",
            "soft": True,
            "name": "10. Soft assert still on login (or public auth)",
        },
        {"action": "screenshot", "name": "11. Screenshot — bad password"},
    ]


def build_auth_login_creds_only_steps(
    *,
    target_url: str,
    email: str = "",
    password: str = "",
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    entry = target_url.rstrip("/") + "/"
    return [
        {"action": "navigate", "url": entry, "name": "1. Open main AM app home"},
        {
            "action": "wait_for_login",
            "timeout_ms": 60000,
            "name": "2. Wait for Flutter login form",
        },
        {
            "action": "assert_text_visible",
            "texts": ["Sign In"],
            "name": "3. Assert Sign In visible",
        },
        {
            "action": "assert_text_visible",
            "texts": ["Email", "Password"],
            "soft": True,
            "name": "4. Assert credential fields present",
        },
        {"action": "screenshot", "name": "5. Screenshot — credentials mode (no Demo Login)"},
    ]


def build_auth_forgot_open_steps(
    *,
    target_url: str,
    email: str = "",
    password: str = "",
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    return [
        *_open_public(target_url, R.FORGOT_PASSWORD, title="forgot-password page"),
        {
            "action": "assert_text_visible",
            "texts": ["Forgot password?"],
            "name": "4. Assert Forgot password heading",
        },
        {
            "action": "assert_text_visible",
            "texts": ["Send Reset Link"],
            "name": "5. Assert Send Reset Link",
        },
        {
            "action": "assert_url_contains",
            "pattern": R.FORGOT_PASSWORD,
            "name": "6. Assert URL contains /forgot-password",
        },
    ]


def build_auth_forgot_submit_steps(
    *,
    target_url: str,
    email: str,
    password: str = "",
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    return [
        *_open_public(target_url, R.FORGOT_PASSWORD, title="forgot-password page"),
        {
            "action": "fill_label",
            "label": "Email address",
            "text": email,
            "name": "4. Fill Email address",
        },
        {
            "action": "click_button",
            "name_match": "Send Reset Link",
            "name": "5. Click Send Reset Link",
        },
        {"action": "wait", "ms": 5000, "name": "6. Wait for reset response"},
        {
            "action": "assert_text_visible",
            "texts": [
                "Password reset instructions",
                "reset",
                "email",
                "sent",
                "Sign In",
            ],
            "soft": True,
            "name": "7. Assert confirmation / success UI",
        },
        {"action": "screenshot", "name": "8. Screenshot — forgot submit result"},
    ]


def build_auth_google_cta_steps(
    *,
    target_url: str,
    email: str = "",
    password: str = "",
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    entry = target_url.rstrip("/") + "/"
    return [
        {"action": "navigate", "url": entry, "name": "1. Open main AM app home"},
        {
            "action": "wait_for_login",
            "timeout_ms": 60000,
            "name": "2. Wait for Flutter login form",
        },
        {
            "action": "assert_text_visible",
            "texts": ["Continue with Google"],
            "name": "3. Assert Continue with Google CTA",
        },
        {"action": "screenshot", "name": "4. Screenshot — Google CTA"},
    ]


def build_auth_google_redirect_steps(
    *,
    target_url: str,
    email: str = "",
    password: str = "",
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    entry = target_url.rstrip("/") + "/"
    return [
        {"action": "navigate", "url": entry, "name": "1. Open main AM app home"},
        {
            "action": "wait_for_login",
            "timeout_ms": 60000,
            "name": "2. Wait for Flutter login form",
        },
        {
            "action": "click_button",
            "name_match": "Continue with Google",
            "name": "3. Click Continue with Google",
        },
        {"action": "wait", "ms": 4000, "name": "4. Wait for OAuth surface"},
        {
            "action": "assert_url_contains",
            "pattern": "accounts.google.com",
            "soft": True,
            "name": "5. Soft assert Google OAuth host (popup OK on web)",
        },
        {
            "action": "assert_text_visible",
            "texts": ["Google", "Continue with Google", "Sign in"],
            "soft": True,
            "name": "6. Soft assert Google sign-in surface",
        },
        {"action": "screenshot", "name": "7. Screenshot — stop before Google credentials"},
    ]


def build_auth_reset_page_open_steps(
    *,
    target_url: str,
    email: str = "",
    password: str = "",
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    return [
        *_open_public(target_url, R.RESET_PASSWORD, title="reset-password page"),
        {
            "action": "assert_text_visible",
            "texts": ["Reset", "password", "Password", "New password", "Confirm"],
            "soft": True,
            "name": "4. Soft assert reset-password chrome",
        },
        {
            "action": "assert_url_contains",
            "pattern": R.RESET_PASSWORD,
            "soft": True,
            "name": "5. Soft assert URL contains /reset-password",
        },
        {"action": "screenshot", "name": "6. Screenshot — reset-password shell"},
    ]


def build_auth_sessions_list_ui_steps(
    *,
    target_url: str,
    email: str,
    password: str,
    login_mode: str = "credentials",
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    from ui_evidence.profiles.modern_ui.session import build_domain_prefix

    prefix = build_domain_prefix(
        target_url, login_mode=login_mode, email=email, password=password
    )
    n = len(prefix) + 1
    return [
        *prefix,
        {
            "action": "navigate_app",
            "path": R.PROFILE,
            "name": f"{n}. Open profile",
        },
        {
            "action": "wait_for_url",
            "pattern": R.PROFILE,
            "timeout_ms": 45000,
            "name": f"{n + 1}. Wait for profile URL",
        },
        {
            "action": "assert_text_visible",
            "texts": [
                "Profile",
                "Security",
                "Session",
                "Devices",
                "Sign out",
                "Logout",
                "Account",
            ],
            "soft": True,
            "name": f"{n + 2}. Soft assert profile / session chrome",
        },
        {"action": "screenshot", "name": f"{n + 3}. Screenshot — sessions surface"},
    ]


def build_auth_logout_ui_steps(
    *,
    target_url: str,
    email: str,
    password: str,
    login_mode: str = "credentials",
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    from ui_evidence.profiles.modern_ui.session import build_domain_prefix

    prefix = build_domain_prefix(
        target_url, login_mode=login_mode, email=email, password=password
    )
    n = len(prefix) + 1
    return [
        *prefix,
        {
            "action": "navigate_app",
            "path": R.PROFILE,
            "name": f"{n}. Open profile for logout",
        },
        {"action": "wait", "ms": 2000, "name": f"{n + 1}. Settle profile"},
        {
            "action": "click_button",
            "name_match": "Sign out",
            "soft": True,
            "name": f"{n + 2}. Click Sign out (soft if menu differs)",
        },
        {
            "action": "click_button",
            "name_match": "Logout",
            "soft": True,
            "name": f"{n + 3}. Click Logout fallback (soft)",
        },
        {"action": "wait", "ms": 4000, "name": f"{n + 4}. Wait after logout"},
        {
            "action": "assert_text_visible",
            "texts": ["Sign In", "Continue with Google", "Email"],
            "soft": True,
            "name": f"{n + 5}. Soft assert returned to public auth",
        },
        {"action": "screenshot", "name": f"{n + 6}. Screenshot — after logout"},
    ]


def build_auth_reg_submit_nonprod_steps(
    *,
    target_url: str,
    email: str = "",
    password: str = "",
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    """Full register submit — skip hard fail on prod hosts."""
    host = target_url.lower()
    prod = "am.asrax.in" in host and "preprod" not in host and "dev" not in host
    unique = f"qa+flow{int(time.time())}@asrax.in"
    steps: list[dict[str, Any]] = [
        *_open_public(target_url, R.REGISTER, title="register page (nonprod submit)"),
        {
            "action": "fill_label",
            "label": "Full name",
            "text": "QA Flow User",
            "name": "4. Fill Full name",
        },
        {
            "action": "fill_label",
            "label": "Email address",
            "text": unique,
            "name": "5. Fill unique Email",
        },
        {
            "action": "fill_label",
            "label": "Password",
            "text": password or "QaFlow!23456",
            "name": "6. Fill Password",
        },
        {
            "action": "fill_label",
            "label": "Confirm password",
            "text": password or "QaFlow!23456",
            "name": "7. Fill Confirm password",
        },
    ]
    if prod:
        steps.extend(
            [
                {
                    "action": "assert_text_visible",
                    "texts": ["Create Account"],
                    "name": "8. Prod guard — do not submit Create Account",
                },
                {
                    "action": "screenshot",
                    "name": "9. Screenshot — prod register fill only",
                },
            ]
        )
        return steps
    steps.extend(
        [
            {
                "action": "click_button",
                "name_match": "Create Account",
                "name": "8. Submit Create Account (nonprod)",
            },
            {"action": "wait", "ms": 6000, "name": "9. Wait for register response"},
            {
                "action": "assert_text_visible",
                "texts": [
                    "verify",
                    "email",
                    "success",
                    "created",
                    "Sign In",
                    "Check your email",
                ],
                "soft": True,
                "name": "10. Soft assert verify/success chrome",
            },
            {"action": "screenshot", "name": "11. Screenshot — register submit result"},
        ]
    )
    return steps


AUTH_SCENARIO_BUILDERS: dict[str, Any] = {
    "AUTH_REG_OPEN": build_auth_reg_open_steps,
    "AUTH_REG_VALIDATION": build_auth_reg_validation_steps,
    "AUTH_REG_FILL": build_auth_reg_fill_steps,
    "AUTH_REG_SUBMIT_NONPROD": build_auth_reg_submit_nonprod_steps,
    "AUTH_LOGIN_OK": build_auth_login_ok_steps,
    "AUTH_LOGIN_BAD_PW": build_auth_login_bad_pw_steps,
    "AUTH_LOGIN_CREDS_ONLY": build_auth_login_creds_only_steps,
    "AUTH_FORGOT_OPEN": build_auth_forgot_open_steps,
    "AUTH_FORGOT_SUBMIT": build_auth_forgot_submit_steps,
    "AUTH_RESET_PAGE_OPEN": build_auth_reset_page_open_steps,
    "AUTH_GOOGLE_CTA": build_auth_google_cta_steps,
    "AUTH_GOOGLE_REDIRECT": build_auth_google_redirect_steps,
    "AUTH_SESSIONS_LIST_UI": build_auth_sessions_list_ui_steps,
    "AUTH_LOGOUT_UI": build_auth_logout_ui_steps,
}


def auth_scenario_verification_checklist(
    steps: list[dict[str, Any]], action_log: list[dict[str, Any]]
) -> list[dict[str, str]]:
    return checklist_from_steps(steps, action_log)


# Re-export for registry convenience
__all__ = [
    "AUTH_SCENARIO_BUILDERS",
    "auth_scenario_verification_checklist",
    "auth_verification_checklist",
]
