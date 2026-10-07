"""Load typed prompt bundles from qa-agent/prompts/."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


def prompts_root() -> Path:
    return Path(__file__).resolve().parent


@dataclass
class PromptBundle:
    """Resolved assets for one prompt type."""

    type_name: str
    type_dir: Path
    type_cfg: dict[str, Any]
    system: str
    user_template: str
    bans: dict[str, Any] = field(default_factory=dict)
    playbooks: dict[str, str] = field(default_factory=dict)

    @property
    def preferred_models(self) -> list[str]:
        raw = self.type_cfg.get("preferred_models") or []
        return [str(x) for x in raw if x]

    @property
    def max_invent_calls(self) -> int:
        return int(self.type_cfg.get("max_invent_calls") or 2)

    @property
    def scenarios_per_skill_default(self) -> int:
        return int(self.type_cfg.get("scenarios_per_skill_default") or 2)

    @property
    def schema_version(self) -> str:
        return str(self.type_cfg.get("schema_version") or "")


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"prompt asset missing: {path}")
    return path.read_text(encoding="utf-8")


def load_registry() -> dict[str, Any]:
    path = prompts_root() / "registry.yaml"
    data = yaml.safe_load(_read_text(path)) or {}
    if not isinstance(data, dict):
        raise ValueError("prompts/registry.yaml must be a mapping")
    return data


def load_prompt_type(
    type_name: str,
    *,
    skill_ids: Optional[list[str]] = None,
    require_playbooks: bool = True,
) -> PromptBundle:
    """
    Resolve a prompt type by name from the root registry.
    Fail closed if type, type.yaml, or required skill playbooks are missing.
    """
    name = (type_name or "").strip()
    if not name:
        raise ValueError("prompt type name is required")

    reg = load_registry()
    types = reg.get("types") or {}
    if name not in types:
        known = ", ".join(sorted(types)) or "(none)"
        raise KeyError(f"unknown prompt type '{name}'; known: {known}")

    entry = types[name] or {}
    rel = str(entry.get("path") or f"{name}/").strip().rstrip("/") + "/"
    type_dir = (prompts_root() / rel).resolve()
    if not type_dir.is_dir():
        raise FileNotFoundError(f"prompt type directory missing: {type_dir}")

    type_cfg_path = type_dir / "type.yaml"
    if not type_cfg_path.is_file():
        raise FileNotFoundError(
            f"prompt type '{name}' has no type.yaml (not implemented yet): {type_cfg_path}"
        )

    type_cfg = yaml.safe_load(_read_text(type_cfg_path)) or {}
    if not isinstance(type_cfg, dict):
        raise ValueError(f"{type_cfg_path} must be a mapping")

    system_name = str(type_cfg.get("system") or "system.md")
    user_name = str(type_cfg.get("user_template") or "user.tmpl.md")
    system = _read_text(type_dir / system_name)
    user_template = _read_text(type_dir / user_name)

    bans: dict[str, Any] = {}
    bans_rel = type_cfg.get("bans")
    if bans_rel:
        bans_path = type_dir / str(bans_rel)
        if bans_path.is_file():
            loaded = yaml.safe_load(_read_text(bans_path)) or {}
            if isinstance(loaded, dict):
                bans = loaded

    playbooks: dict[str, str] = {}
    skills_dir_name = str(type_cfg.get("skills_dir") or "skills")
    skills_dir = type_dir / skills_dir_name
    ids = list(skill_ids or [])
    if ids and require_playbooks:
        if not skills_dir.is_dir():
            raise FileNotFoundError(f"skills_dir missing for type '{name}': {skills_dir}")
        missing: list[str] = []
        for sid in ids:
            p = skills_dir / f"{sid}.md"
            if not p.is_file():
                missing.append(sid)
                continue
            playbooks[sid] = _read_text(p)
        if missing:
            raise FileNotFoundError(
                f"prompt type '{name}' missing playbooks for: {', '.join(missing)}"
            )
    elif skills_dir.is_dir() and not ids:
        for p in sorted(skills_dir.glob("*.md")):
            playbooks[p.stem] = _read_text(p)

    return PromptBundle(
        type_name=name,
        type_dir=type_dir,
        type_cfg=type_cfg,
        system=system,
        user_template=user_template,
        bans=bans,
        playbooks=playbooks,
    )
