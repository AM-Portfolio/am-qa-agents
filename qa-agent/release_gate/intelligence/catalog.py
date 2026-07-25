"""SPT / playbook catalog reader (ADR-004 style)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def _catalog_root() -> Path:
    env = os.getenv("QA_AGENT_CATALOG_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[1] / "catalog"


def load_spt_playbooks() -> list[dict[str, Any]]:
    root = _catalog_root() / "spt"
    if not root.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.yaml")):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if isinstance(data, dict):
            data.setdefault("id", path.stem)
            data.setdefault("source", str(path.name))
            items.append(data)
    return items


def playbook_candidates_for_repo(repo: str) -> list[dict[str, Any]]:
    short = repo.split("/")[-1] if repo else ""
    out = []
    for pb in load_spt_playbooks():
        repos = pb.get("repos") or []
        if not repos or short in repos or repo in repos:
            out.append(pb)
    return out


def spt_priority(playbook: dict[str, Any]) -> float:
    return float(playbook.get("priority") or 50)
