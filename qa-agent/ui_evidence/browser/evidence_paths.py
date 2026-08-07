from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


def profile_evidence_prefix(profile: str | None) -> str:
    """Map AUTH_FLOW_MAIN -> auth, PORTFOLIO_SMOKE_FLOW -> portfolio, etc."""
    p = (profile or "ui").upper().replace("-", "_")
    ordered = (
        ("AUTH", "auth"),
        ("DASHBOARD", "dashboard"),
        ("PORTFOLIO", "portfolio"),
        ("TRADE", "trade"),
        ("MARKET", "market"),
        ("DOC", "doc"),
        ("SUBSCRIPTION", "subscription"),
        ("PROFILE", "profile"),
        ("ADMIN", "admin"),
    )
    for key, prefix in ordered:
        if key in p:
            return prefix
    return "ui"


def short_test_id(test_id: str) -> str:
    return (test_id or "").replace("-", "")[:8] or "run"


def evidence_run_dirname(profile: str | None, test_id: str, when: datetime | None = None) -> str:
    stamp = (when or datetime.now()).strftime("%Y%m%d-%H%M%S")
    return f"{profile_evidence_prefix(profile)}-{stamp}-{short_test_id(test_id)}"


def slugify_step_name(name: str | None) -> str:
    raw = (name or "step").strip()
    raw = re.sub(r"^\d+\.\s*", "", raw)
    raw = re.sub(r"(?i)^screenshot\s*[—\-:]\s*", "", raw)
    raw = re.sub(r"[^a-zA-Z0-9]+", "-", raw).strip("-").lower()
    return (raw or "step")[:60]


def step_screenshot_filename(
    index: int,
    *,
    step_name: str | None = None,
    when: datetime | None = None,
) -> str:
    """1-based index; includes capture time + readable step slug."""
    stamp = (when or datetime.now()).strftime("%H%M%S")
    slug = slugify_step_name(step_name)
    return f"{int(index):03d}-{stamp}-{slug}.png"


def resolve_screenshot_dir(
    report_dir: Path,
    *,
    test_id: str,
    evidence_dirname: str | None = None,
) -> Path:
    root = Path(report_dir) / "screenshots"
    if evidence_dirname:
        return root / evidence_dirname
    legacy = root / test_id
    if legacy.is_dir():
        return legacy
    short = short_test_id(test_id)
    matches = sorted(root.glob(f"*-{short}")) if root.is_dir() else []
    if matches:
        return matches[-1]
    return legacy
