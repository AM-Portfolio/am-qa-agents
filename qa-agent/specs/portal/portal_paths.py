"""Resolve qa-portal-ui assets — HTML legacy and/or Flutter web build."""
from __future__ import annotations

import os
from pathlib import Path


def _repo_root_from_app() -> Path:
    # qa-agent/specs/portal → monorepo root (parents[3])
    return Path(__file__).resolve().parents[3]


def portal_ui_root() -> Path:
    """
    Order:
    1. SPT_PORTAL_UI_DIR / QA_PORTAL_UI_DIR
    2. Monorepo sibling qa-portal-ui
    3. /portal-ui (container)
    4. Legacy app/ next to this file
    """
    for key in ("SPT_PORTAL_UI_DIR", "QA_PORTAL_UI_DIR"):
        raw = (os.environ.get(key) or "").strip()
        if raw:
            p = Path(raw)
            if p.is_dir():
                return p.resolve()

    mono = _repo_root_from_app() / "qa-portal-ui"
    if mono.is_dir():
        return mono

    container = Path("/portal-ui")
    if container.is_dir():
        return container

    return Path(__file__).resolve().parent


def portal_static_dir() -> Path:
    return portal_ui_root() / "static"


def portal_template_path() -> Path:
    return portal_ui_root() / "templates" / "portal.html"


def portal_flutter_web_dir() -> Path | None:
    """Directory containing Flutter web index.html (build/web or /portal-flutter)."""
    for key in ("SPT_PORTAL_FLUTTER_DIR", "QA_PORTAL_FLUTTER_DIR"):
        raw = (os.environ.get(key) or "").strip()
        if raw:
            p = Path(raw)
            if (p / "index.html").is_file():
                return p.resolve()

    candidates = [
        portal_ui_root() / "build" / "web",
        Path("/portal-flutter"),
        _repo_root_from_app() / "qa-portal-ui" / "build" / "web",
    ]
    for p in candidates:
        if (p / "index.html").is_file():
            return p.resolve()
    return None


def flutter_portal_available() -> bool:
    return portal_flutter_web_dir() is not None
