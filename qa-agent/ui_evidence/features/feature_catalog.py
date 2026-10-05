"""Parse Cucumber-style .feature files → ordered (scenario, profile) pairs."""
from __future__ import annotations

import re
from pathlib import Path

FEATURES_ROOT = Path(__file__).resolve().parent

# Core auth module (existing)
AUTH_FEATURE_FILES = (
    "auth/user_registration.feature",
    "auth/user_login.feature",
    "auth/forgot_password.feature",
    "auth/google_login.feature",
)

# Full flow pack: sessions/logout + lifecycle + reset + subscription
AUTH_USER_FULL_FLOW_FILES = (
    *AUTH_FEATURE_FILES,
    "auth/password_reset.feature",
    "auth/user_sessions.feature",
    "auth/user_lifecycle.feature",
    "subscription/subscription_plans.feature",
)

_SCENARIO_RE = re.compile(r"^\s*Scenario:\s*(.+?)\s*$")
_PROFILE_TAG_RE = re.compile(r"@profile:([A-Z0-9_]+)")


def parse_feature_file(path: Path) -> list[tuple[str, str]]:
    """Return [(scenario_name, profile_id), ...] in file order."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    out: list[tuple[str, str]] = []
    pending_profile: str | None = None
    for line in lines:
        tag_m = _PROFILE_TAG_RE.search(line)
        if tag_m:
            pending_profile = tag_m.group(1)
            continue
        scen_m = _SCENARIO_RE.match(line)
        if scen_m:
            name = scen_m.group(1).strip()
            if not pending_profile:
                raise ValueError(f"{path}: Scenario {name!r} missing @profile: tag")
            out.append((name, pending_profile))
            pending_profile = None
    return out


def _profiles_from_files(
    files: tuple[str, ...], *, root: Path | None = None
) -> tuple[str, ...]:
    base = root or FEATURES_ROOT
    rows: list[str] = []
    for rel in files:
        path = base / rel
        if not path.is_file():
            raise FileNotFoundError(path)
        for _scenario, profile in parse_feature_file(path):
            rows.append(profile)
    return tuple(rows)


def auth_feature_scenarios(*, root: Path | None = None) -> list[tuple[str, str, str]]:
    """Return [(feature_rel, scenario_name, profile_id), ...] in suite order."""
    base = root or FEATURES_ROOT
    rows: list[tuple[str, str, str]] = []
    for rel in AUTH_FEATURE_FILES:
        path = base / rel
        if not path.is_file():
            raise FileNotFoundError(path)
        for scenario, profile in parse_feature_file(path):
            rows.append((rel, scenario, profile))
    return rows


def auth_user_module_profiles(*, root: Path | None = None) -> tuple[str, ...]:
    return tuple(p for _, _, p in auth_feature_scenarios(root=root))


def auth_user_full_flow_profiles(*, root: Path | None = None) -> tuple[str, ...]:
    return _profiles_from_files(AUTH_USER_FULL_FLOW_FILES, root=root)


def auth_user_full_flow_scenarios(
    *, root: Path | None = None
) -> list[tuple[str, str, str]]:
    base = root or FEATURES_ROOT
    rows: list[tuple[str, str, str]] = []
    for rel in AUTH_USER_FULL_FLOW_FILES:
        path = base / rel
        if not path.is_file():
            raise FileNotFoundError(path)
        for scenario, profile in parse_feature_file(path):
            rows.append((rel, scenario, profile))
    return rows
