"""Shared types for test profile plugins."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class TargetConfig:
    """Resolved test target from a wrapper targets file or agent settings."""

    base_url: str
    ui_mode: Literal["portfolio", "main"] = "main"
    auth_login_mode: Literal["demo", "credentials"] = "demo"
    profile: str = "AUTH_FLOW_MAIN"
    module: str = "modern-ui"
    environment: str = "preprod"
    persona: str = "demo_user"
    portfolio_id: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    viewport_width: int | None = None
    viewport_height: int | None = None
