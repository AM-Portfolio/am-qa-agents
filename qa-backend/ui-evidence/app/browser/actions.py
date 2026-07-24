from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

_DEMO_LOGIN_BUTTON = re.compile(r"Demo Login|Try Demo|Quick Login", re.IGNORECASE)
_NAV_TITLES = re.compile(
    r"^(Dashboard|Portfolio|Trade|Market|AI Chat|Analysis|Profile|Doc Intel|Subscription)$",
    re.IGNORECASE,
)


async def _enable_flutter_accessibility(page) -> None:
    """Flutter web hides semantics until the placeholder is activated."""
    await page.evaluate(
        """() => {
            const el = document.querySelector('flt-semantics-placeholder[aria-label="Enable accessibility"]');
            if (el) el.click();
        }"""
    )
    await page.wait_for_timeout(1500)


async def _wait_for_flutter(page, timeout_ms: int) -> None:
    await page.wait_for_load_state("load", timeout=min(timeout_ms, 90000))
    try:
        await page.wait_for_function(
            """() => {
                const pane = document.querySelector('flt-glass-pane')
                    || document.querySelector('flutter-view')
                    || document.querySelector('flt-scene-host');
                if (!pane) return false;
                const rect = pane.getBoundingClientRect();
                return rect.width > 100 && rect.height > 100;
            }""",
            timeout=min(timeout_ms, 90000),
        )
    except Exception:
        pass
    await page.wait_for_timeout(3000)


async def _wait_for_login_form(page, timeout_ms: int) -> None:
    await _wait_for_flutter(page, timeout_ms)
    await _enable_flutter_accessibility(page)
    deadline = time.monotonic() + (timeout_ms / 1000)
    locators = [
        page.get_by_label(re.compile(r"email", re.I)),
        page.get_by_placeholder("Enter your email"),
        page.get_by_placeholder("Email / User ID"),
        page.get_by_role("textbox").first,
        page.get_by_role(
            "button",
            name=re.compile(r"Sign In|Developer Options|Demo Login|Try Demo", re.I),
        ),
        page.get_by_text(
            re.compile(r"Portfolio Login|Welcome Back|Forgot Password", re.I)
        ),
    ]
    last_error = "Login form not visible"
    while time.monotonic() < deadline:
        for locator in locators:
            try:
                if await locator.count() > 0 and await locator.first.is_visible():
                    return
            except Exception as exc:
                last_error = str(exc)
        await page.wait_for_timeout(750)
    raise TimeoutError(f"Login form not visible after {timeout_ms}ms: {last_error}")


async def _click_demo_login(page) -> None:
    for pattern in (_DEMO_LOGIN_BUTTON,):
        button = page.get_by_role("button", name=pattern).first
        try:
            if await button.is_visible():
                await button.click(timeout=20000)
                return
        except Exception:
            pass

    dev_options = page.get_by_role(
        "button", name=re.compile(r"Developer Options", re.IGNORECASE)
    ).first
    await dev_options.click(timeout=20000)
    await page.wait_for_timeout(500)
    await page.get_by_role("button", name=_DEMO_LOGIN_BUTTON).first.click(timeout=20000)


async def _wait_for_url(page, pattern: str, timeout_ms: int) -> None:
    deadline = time.monotonic() + (timeout_ms / 1000)
    while time.monotonic() < deadline:
        if pattern in (page.url or ""):
            return
        await page.wait_for_timeout(400)
    raise TimeoutError(f"URL did not contain {pattern!r} within {timeout_ms}ms (now={page.url})")


async def _wait_for_module(page, module: str, timeout_ms: int) -> None:
    await _wait_for_flutter(page, timeout_ms)
    await _enable_flutter_accessibility(page)
    # Skip past deferred skeleton text if present
    deadline = time.monotonic() + (timeout_ms / 1000)
    loading = re.compile(rf"Loading\s+{re.escape(module)}", re.I)
    while time.monotonic() < deadline:
        try:
            count = await page.get_by_text(loading).count()
            if count == 0:
                return
        except Exception:
            return
        await page.wait_for_timeout(500)
    # Soft: module may not show Loading text — still OK after flutter wait


async def _click_nav(page, title: str) -> None:
    await _enable_flutter_accessibility(page)
    pattern = re.compile(rf"^{re.escape(title)}$", re.I)
    # Prefer role=link / button / text
    for getter in (
        lambda: page.get_by_role("link", name=pattern).first,
        lambda: page.get_by_role("button", name=pattern).first,
        lambda: page.get_by_text(pattern).first,
    ):
        loc = getter()
        try:
            if await loc.count() > 0 and await loc.is_visible():
                await loc.click(timeout=20000)
                return
        except Exception:
            continue
    raise RuntimeError(f"Nav title {title!r} not clickable")


async def _assert_no_error_banner(page) -> None:
    patterns = [
        re.compile(r"Something went wrong", re.I),
        re.compile(r"Unexpected error", re.I),
        re.compile(r"Failed to load", re.I),
        re.compile(r"Internal Server Error", re.I),
    ]
    for pat in patterns:
        try:
            loc = page.get_by_text(pat).first
            if await loc.count() > 0 and await loc.is_visible():
                text = await loc.inner_text()
                raise RuntimeError(f"Error banner visible: {text[:120]}")
        except RuntimeError:
            raise
        except Exception:
            continue


async def run_browser_action(page, step: dict[str, Any], ctx) -> None:
    action = step.get("action")
    name = step.get("name", action)
    retries = int(step.get("retries", getattr(ctx, "step_retry_count", 0) or 0))
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            await _run_browser_action_once(page, step, ctx, action, name)
            return
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                logger.warning("[%s] retry %d after: %s", name, attempt + 1, exc)
                await page.wait_for_timeout(1000)
            else:
                raise
    if last_exc:
        raise last_exc


async def _run_browser_action_once(page, step: dict[str, Any], ctx, action: str, name: str) -> None:
    if action == "navigate":
        url = step["url"]
        logger.info("[%s] Navigate → %s", name, url)
        response = await page.goto(url, wait_until="load", timeout=90000)
        if response and response.status >= 400 and not step.get("allow_http_error"):
            raise RuntimeError(f"Navigation failed HTTP {response.status} for {url}")
        ctx.log_action(
            "navigate", step=name, url=url, status=response.status if response else None
        )

    elif action == "navigate_app":
        path = step["path"]
        base = step.get("base_url") or getattr(ctx, "base_url", None) or page.url
        # strip to origin
        from urllib.parse import urlsplit, urlunsplit

        parts = urlsplit(base)
        origin = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
        url = urljoin(origin.rstrip("/") + "/", path.lstrip("/"))
        logger.info("[%s] Navigate app → %s", name, url)
        response = await page.goto(url, wait_until="load", timeout=90000)
        if response and response.status >= 400 and not step.get("allow_http_error"):
            raise RuntimeError(f"Navigation failed HTTP {response.status} for {url}")
        await _enable_flutter_accessibility(page)
        ctx.log_action(
            "navigate_app", step=name, url=url, path=path, status=response.status if response else None
        )

    elif action == "wait":
        ms = int(step.get("ms", 1000))
        await page.wait_for_timeout(ms)
        ctx.log_action("wait", step=name, ms=ms)

    elif action == "wait_for_label":
        label = step["label"]
        timeout = int(step.get("timeout_ms", 30000))
        logger.info("[%s] Waiting for label %r", name, label)
        await page.get_by_label(label).first.wait_for(state="visible", timeout=timeout)
        ctx.log_action("wait_for_label", step=name, label=label)

    elif action == "wait_for_flutter":
        timeout = int(step.get("timeout_ms", 60000))
        logger.info("[%s] Waiting for Flutter web bootstrap", name)
        await _wait_for_flutter(page, timeout)
        ctx.log_action("wait_for_flutter", step=name, timeout_ms=timeout)

    elif action == "wait_for_login":
        timeout = int(step.get("timeout_ms", 45000))
        logger.info("[%s] Waiting for login form", name)
        await _wait_for_login_form(page, timeout)
        ctx.log_action("wait_for_login", step=name, timeout_ms=timeout)

    elif action == "wait_for_url":
        pattern = step["pattern"]
        timeout = int(step.get("timeout_ms", 45000))
        logger.info("[%s] Waiting for URL containing %r", name, pattern)
        await _wait_for_url(page, pattern, timeout)
        ctx.log_action("wait_for_url", step=name, pattern=pattern, url=page.url)

    elif action == "wait_for_module":
        module = step.get("module", "App")
        timeout = int(step.get("timeout_ms", 60000))
        logger.info("[%s] Waiting for module %r", name, module)
        await _wait_for_module(page, module, timeout)
        ctx.log_action("wait_for_module", step=name, module=module)

    elif action == "fill_label":
        label = step["label"]
        text = step["text"]
        logger.info("[%s] Fill label %r", name, label)
        await page.get_by_label(label).first.fill(text, timeout=15000)
        ctx.log_action("fill_label", step=name, label=label)

    elif action == "click_button":
        name_match = step.get("name_match", step.get("text", ""))
        logger.info("[%s] Click button matching %r", name, name_match)
        pattern = re.compile(name_match, re.IGNORECASE)
        await page.get_by_role("button", name=pattern).first.click(timeout=20000)
        ctx.log_action("click_button", step=name, button=name_match)

    elif action == "click_demo_login":
        logger.info("[%s] Click Demo Login (login section)", name)
        await _click_demo_login(page)
        ctx.log_action("click_demo_login", step=name)

    elif action == "click_nav":
        title = step.get("title") or step.get("text") or ""
        logger.info("[%s] Click nav %r", name, title)
        await _click_nav(page, title)
        ctx.log_action("click_nav", step=name, title=title)

    elif action == "click_text":
        text = step.get("text") or ""
        logger.info("[%s] Click text %r", name, text)
        await _enable_flutter_accessibility(page)
        await page.get_by_text(text, exact=False).first.click(timeout=20000)
        ctx.log_action("click_text", step=name, text=text)

    elif action == "click":
        selector = step["selector"]
        await page.click(selector, timeout=15000)
        ctx.log_action("click", step=name, selector=selector)

    elif action == "fill":
        await page.fill(step["selector"], step["text"], timeout=15000)
        ctx.log_action("fill", step=name, selector=step["selector"])

    elif action == "upload_file":
        path = Path(step["path"])
        if not path.is_file():
            raise FileNotFoundError(f"Upload fixture missing: {path}")
        logger.info("[%s] Upload file %s", name, path)
        # Flutter file inputs are often hidden — try input[type=file]
        handle = page.locator('input[type="file"]').first
        await handle.set_input_files(str(path), timeout=30000)
        ctx.log_action("upload_file", step=name, path=str(path))

    elif action == "assert_no_error_banner":
        soft = bool(step.get("soft"))
        try:
            await _assert_no_error_banner(page)
            ctx.log_action("assert_pass", step=name, check="no_error_banner")
        except RuntimeError as exc:
            if soft:
                ctx.log_action("assert_soft_fail", step=name, error=str(exc))
                logger.warning("[%s] SOFT: %s", name, exc)
            else:
                raise

    elif action == "screenshot":
        ctx.log_action("screenshot", step=name)

    elif action.startswith("assert_"):
        pass

    else:
        raise ValueError(f"Unknown step action: {action}")
