"""Doc Intel smoke — deep-link /app/doc-intel/*."""
from __future__ import annotations

from typing import Any

from app.profiles.modern_ui import routes as R
from app.profiles.modern_ui.session import build_domain_prefix, checklist_from_steps


def build_doc_intel_flow_steps(
    *,
    target_url: str,
    email: str = "",
    password: str = "",
    login_mode: str = "demo",
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    prefix = build_domain_prefix(
        target_url, login_mode=login_mode, email=email, password=password
    )
    n = len(prefix) + 1
    processor = R.doc_intel_path("doc-processor")
    extractor = R.doc_intel_path("email-extractor")
    return [
        *prefix,
        {
            "action": "navigate_app",
            "path": processor,
            "name": f"{n}. Deep-link doc processor",
        },
        {
            "action": "wait_for_module",
            "module": "Doc",
            "timeout_ms": 90000,
            "name": f"{n + 1}. Wait for doc-intel module",
        },
        {
            "action": "assert_url_contains",
            "pattern": "/app/doc-intel",
            "name": f"{n + 2}. Assert doc-intel URL",
        },
        {
            "action": "assert_text_visible",
            "texts": ["Document", "Upload", "Doc"],
            "soft": True,
            "name": f"{n + 3}. Soft-assert doc processor chrome",
        },
        {
            "action": "assert_no_error_banner",
            "soft": True,
            "name": f"{n + 4}. Soft-assert no error banner",
        },
        {"action": "screenshot", "name": f"{n + 5}. Screenshot — doc processor"},
        {
            "action": "navigate_app",
            "path": extractor,
            "name": f"{n + 6}. Deep-link email extractor",
        },
        {
            "action": "wait_for_url",
            "pattern": "email-extractor",
            "timeout_ms": 45000,
            "name": f"{n + 7}. Wait for email-extractor tab",
        },
        {
            "action": "assert_url_contains",
            "pattern": "email-extractor",
            "name": f"{n + 8}. Assert email-extractor URL",
        },
        {"action": "screenshot", "name": f"{n + 9}. Screenshot — email extractor"},
    ]


def build_doc_upload_flow_steps(
    *,
    target_url: str,
    email: str = "",
    password: str = "",
    login_mode: str = "demo",
    upload_file: str | None = None,
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    steps = build_doc_intel_flow_steps(
        target_url=target_url,
        email=email,
        password=password,
        login_mode=login_mode,
    )
    if not upload_file:
        return steps
    n = len(steps) + 1
    steps.extend(
        [
            {
                "action": "navigate_app",
                "path": R.doc_intel_path("doc-processor"),
                "name": f"{n}. Return to doc processor for upload",
            },
            {
                "action": "upload_file",
                "path": upload_file,
                "name": f"{n + 1}. Upload fixture document",
            },
            {"action": "wait", "ms": 3000, "name": f"{n + 2}. Wait after upload"},
            {"action": "screenshot", "name": f"{n + 3}. Screenshot — after upload"},
        ]
    )
    return steps


def doc_intel_verification_checklist(
    steps: list[dict[str, Any]], action_log: list[dict[str, Any]]
) -> list[dict[str, str]]:
    return checklist_from_steps(steps, action_log)
