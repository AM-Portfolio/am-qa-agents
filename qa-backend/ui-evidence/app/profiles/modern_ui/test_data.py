"""Personas and fixture paths for modern-ui UI tests."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.config import settings

_CATALOG = Path(__file__).resolve().parents[2] / "catalog" / "test_data.yaml"
_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def load_test_data() -> dict[str, Any]:
    if not _CATALOG.is_file():
        return {"personas": {}, "defaults": {}}
    return yaml.safe_load(_CATALOG.read_text(encoding="utf-8")) or {}


def resolve_persona(name: str | None) -> dict[str, Any]:
    data = load_test_data()
    personas = data.get("personas") or {}
    key = (name or data.get("defaults", {}).get("persona") or "demo_user").strip()
    persona = dict(personas.get(key) or personas.get("demo_user") or {})
    persona.setdefault("id", key)
    persona.setdefault("login_mode", "demo")
    if persona.get("login_mode") == "credentials":
        persona.setdefault("email", settings.TEST_USER_EMAIL)
        persona.setdefault("password", settings.TEST_USER_PASSWORD)
    if key == "admin_user":
        persona.setdefault("email", getattr(settings, "TEST_ADMIN_EMAIL", settings.TEST_USER_EMAIL))
        persona.setdefault(
            "password", getattr(settings, "TEST_ADMIN_PASSWORD", settings.TEST_USER_PASSWORD)
        )
        persona["login_mode"] = "credentials"
    return persona


def sample_doc_path() -> Path:
    path = _FIXTURES / "sample-portfolio.pdf"
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        # Minimal PDF bytes so upload_file has something to send
        path.write_bytes(
            b"%PDF-1.1\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
        )
    return path
