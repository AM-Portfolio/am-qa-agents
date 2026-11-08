"""OpenAPI hash drift → needs_reinvent (Phase 6). Knowledge SoT = DB."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from ui_evidence.scenario_bank.bank_store import load_bank, set_flags
from ui_evidence.scenario_bank.repo import get_repo, norm_env


def knowledge_path(plugin_id: str, env: str, *, root: Optional[Path] = None) -> Path:
    """Legacy file path (debug export only)."""
    env_n = norm_env(env)
    base = root or (
        Path(__file__).resolve().parents[1] / "data" / "scenario_bank" / "knowledge"
    )
    return base / f"{plugin_id}_{env_n}.json"


def load_knowledge(
    plugin_id: str,
    env: str,
    *,
    root: Optional[Path] = None,
    service_key: Optional[str] = None,
) -> dict[str, Any]:
    """Prefer DB knowledge; fall back to legacy JSON file if empty."""
    env_n = norm_env(env)
    key = service_key or plugin_id
    db = get_repo().get_knowledge(key, env_n)
    if db:
        return db
    # also try plugin_id key
    if key != plugin_id:
        db = get_repo().get_knowledge(plugin_id, env_n)
        if db:
            return db
    path = knowledge_path(plugin_id, env_n, root=root)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def apply_hash_drift(
    service_key: str,
    env: str,
    *,
    plugin_id: str,
    new_openapi_hash: str,
    knowledge_root: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Compare new smoke hash to prior knowledge (DB).
    Drift → bank needs_reinvent=True (does not invent by itself).
    """
    env_n = norm_env(env)
    prior = load_knowledge(
        plugin_id, env_n, root=knowledge_root, service_key=service_key
    )
    prior_hash = ""
    smoke = prior.get("contract_smoke") or {}
    if isinstance(smoke, dict):
        prior_hash = str(smoke.get("openapi_hash") or "")
    prior_hash = prior_hash or str(prior.get("openapi_hash") or "")

    bank = load_bank(service_key, env_n)
    if not prior_hash:
        return {
            "ok": True,
            "drift": False,
            "reason": "no_prior_hash",
            "prior_hash": prior_hash,
            "new_hash": new_openapi_hash,
            "needs_reinvent": bool(bank.get("needs_reinvent")),
            "invent_complete": bool(bank.get("invent_complete")),
        }

    if prior_hash == new_openapi_hash:
        return {
            "ok": True,
            "drift": False,
            "reason": "hash_match",
            "prior_hash": prior_hash,
            "new_hash": new_openapi_hash,
            "needs_reinvent": bool(bank.get("needs_reinvent")),
            "invent_complete": bool(bank.get("invent_complete")),
        }

    set_flags(service_key, env_n, needs_reinvent=True, invent_complete=False)
    get_repo().upsert_knowledge(
        service_key,
        env_n,
        {
            "openapi_hash": new_openapi_hash,
            "needs_reinvent": True,
            "invent_complete": False,
            "hash_drift": True,
        },
    )
    return {
        "ok": True,
        "drift": True,
        "reason": "hash_mismatch",
        "prior_hash": prior_hash,
        "new_hash": new_openapi_hash,
        "needs_reinvent": True,
        "invent_complete": False,
    }
