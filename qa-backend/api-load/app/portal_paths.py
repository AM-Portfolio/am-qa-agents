"""Resolve qa-portal-ui (SPT operator HTML/JS) — source of truth outside api-load app/."""
from __future__ import annotations

import os
from pathlib import Path


def portal_ui_root() -> Path:
    """
    Order:
    1. SPT_PORTAL_UI_DIR / QA_PORTAL_UI_DIR
    2. Monorepo sibling qa-portal-ui (from qa-backend/api-load/app → repo root)
    3. /portal-ui (container default)
    4. Legacy app/ next to this file (dev fallback)
    """
    for key in ("SPT_PORTAL_UI_DIR", "QA_PORTAL_UI_DIR"):
        raw = (os.environ.get(key) or "").strip()
        if raw:
            p = Path(raw)
            if p.is_dir():
                return p.resolve()

    # parents: app → api-load → qa-backend → am-qa-agents  (parents[2] = repo root)
    here = Path(__file__).resolve().parent
    mono = here.parents[2] / "qa-portal-ui"
    if mono.is_dir() and (mono / "templates" / "portal.html").is_file():
        return mono

    container = Path("/portal-ui")
    if container.is_dir() and (container / "templates" / "portal.html").is_file():
        return container

    return here


def portal_static_dir() -> Path:
    return portal_ui_root() / "static"


def portal_template_path() -> Path:
    return portal_ui_root() / "templates" / "portal.html"
