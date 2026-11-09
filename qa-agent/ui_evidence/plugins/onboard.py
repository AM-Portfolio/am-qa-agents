"""Onboard a QA plugin: contract smoke + hand-seeded data_prep (+ bank stub)."""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Optional

from ui_evidence.plugins.loader import (
    get_plugin,
    run_data_prep,
)

logger = logging.getLogger(__name__)


def _knowledge_dir() -> Path:
    """Writable knowledge root (image FS is read-only for non-root).

    Prefer QA_SCENARIO_BANK_DIR / DATA_DIR; fall back to package tree for local dig.
    """
    import os

    for key in ("QA_SCENARIO_BANK_DIR", "DATA_DIR", "QA_AGENT_ARTIFACT_DIR"):
        raw = (os.getenv(key) or "").strip()
        if not raw:
            continue
        root = Path(raw)
        # ARTIFACT_DIR is …/pdf — use parent data root
        if key == "QA_AGENT_ARTIFACT_DIR":
            root = root.parent
        return root / "scenario_bank" / "knowledge"
    return Path(__file__).resolve().parents[1] / "data" / "scenario_bank" / "knowledge"


def _normalize_env(env: str) -> str:
    e = (env or "dev").strip().lower()
    return "dev" if e == "dig" else e


def contract_smoke(plugin_id: str, env: str) -> dict[str, Any]:
    """Fetch OpenAPI tool count for plugin SPT service; refuse invent if empty."""
    plugin = get_plugin(plugin_id=plugin_id)
    if plugin is None:
        return {"ok": False, "status": "plugin_not_found", "plugin_id": plugin_id}

    env_n = _normalize_env(env)
    contract = plugin.manifest.get("contract") or {}
    min_tools = int(contract.get("min_tools") or 1)
    service = plugin.spt_service_id

    try:
        from specs.openapi_tools.registry import list_tools, refresh_tools_from_prod

        refresh = refresh_tools_from_prod(environment=env_n, services=[service])
        tools = list(list_tools(service=service, limit=1000).get("tools") or [])
    except Exception as exc:  # noqa: BLE001
        logger.warning("contract_smoke failed plugin=%s err=%s", plugin_id, exc)
        return {
            "ok": False,
            "status": "onboard_blocked",
            "plugin_id": plugin_id,
            "env": env_n,
            "error": str(exc),
            "tool_count": 0,
        }

    tool_count = len(tools)
    paths = sorted(
        {
            str((t.get("path") or t.get("operation_path") or ""))
            for t in tools
            if t.get("path") or t.get("operation_path")
        }
    )
    blob = json.dumps(
        {"service": service, "env": env_n, "paths": paths}, sort_keys=True
    )
    openapi_hash = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    ok = tool_count >= min_tools
    return {
        "ok": ok,
        "status": "ok" if ok else "onboard_blocked",
        "plugin_id": plugin_id,
        "env": env_n,
        "service": service,
        "tool_count": tool_count,
        "min_tools": min_tools,
        "openapi_hash": openapi_hash,
        "refresh": refresh if isinstance(refresh, dict) else {},
    }


def onboard_plugin(
    plugin_id: str,
    env: str = "dev",
    *,
    force_llm: bool = False,
    skip_prep: bool = False,
) -> dict[str, Any]:
    """
    Contract smoke → persist knowledge → hand-seeded data_prep.
    Invent (LiteLLM) lands in Phase 5; here we probe LiteLLM and refuse invent if unavailable.
    """
    env_n = _normalize_env(env)
    plugin = get_plugin(plugin_id=plugin_id)
    if plugin is None:
        return {"ok": False, "status": "plugin_not_found", "plugin_id": plugin_id}

    from ui_evidence.scenario_bank.hash_drift import apply_hash_drift
    from ui_evidence.scenario_bank.llm_status import probe_litellm

    litellm = probe_litellm(ping_chat=False)
    smoke = contract_smoke(plugin_id, env_n)
    service_key = str(
        (plugin.manifest.get("scenario_bank") or {}).get("service_key", plugin_id)
    )
    drift = {"ok": True, "drift": False, "reason": "smoke_not_ok"}
    if smoke.get("ok") and smoke.get("openapi_hash"):
        drift = apply_hash_drift(
            service_key,
            env_n,
            plugin_id=plugin_id,
            new_openapi_hash=str(smoke["openapi_hash"]),
            knowledge_root=_knowledge_dir(),
        )
    knowledge = {
        "plugin_id": plugin_id,
        "service_key": service_key,
        "env": env_n,
        "contract_smoke": smoke,
        "openapi_hash": smoke.get("openapi_hash"),
        "invent_complete": False,
        "needs_reinvent": bool(drift.get("needs_reinvent")),
        "hash_drift": drift,
        "force_llm": bool(force_llm),
        "llm_invoked": False,
        "provider": "litellm",
        "litellm_available": bool(litellm.get("available")),
        "litellm_model": litellm.get("model"),
        "seed_skills": list(
            (plugin.manifest.get("scenario_bank") or {}).get("seed_skills") or []
        ),
    }

    kdir = _knowledge_dir()
    kdir.mkdir(parents=True, exist_ok=True)
    kpath = kdir / f"{plugin_id}_{env_n}.json"
    kpath.write_text(json.dumps(knowledge, indent=2), encoding="utf-8")

    prep: dict[str, Any] = {"ok": True, "skipped": True}
    if not skip_prep:
        try:
            prep = run_data_prep(plugin, env_n, ctx={"smoke": smoke})
        except Exception as exc:  # noqa: BLE001
            prep = {"ok": False, "error": str(exc)}
            if env_n in {
                str(x).lower()
                for x in (
                    (plugin.manifest.get("data_prep") or {}).get("fail_closed_envs")
                    or []
                )
            }:
                return {
                    "ok": False,
                    "status": "prep_failed",
                    "plugin_id": plugin_id,
                    "env": env_n,
                    "contract_smoke": smoke,
                    "prep": prep,
                    "knowledge_path": str(kpath),
                }

    bank: dict[str, Any] = {"ok": True, "seeded": 0, "skipped": True}
    seed_skills = list(knowledge.get("seed_skills") or [])
    if seed_skills:
        try:
            from ui_evidence.scenario_bank.bank_store import seed_default_rows

            bank = seed_default_rows(service_key, env_n, seed_skills)
            bank["skipped"] = False
        except Exception as exc:  # noqa: BLE001
            bank = {"ok": False, "error": str(exc), "seeded": 0}

    invent: dict[str, Any] = {
        "ok": True,
        "skipped": True,
        "llm_invoked": False,
        "call_count": 0,
        "reason": "not_attempted",
    }
    llm_invoked = False
    if not smoke.get("ok"):
        invent = {
            "ok": True,
            "skipped": True,
            "llm_invoked": False,
            "call_count": 0,
            "reason": "smoke_blocked",
        }
    elif not litellm.get("available"):
        invent = {
            "ok": True,
            "skipped": True,
            "llm_invoked": False,
            "call_count": 0,
            "reason": "litellm_unavailable",
        }
    else:
        try:
            from ui_evidence.scenario_bank.bank_store import load_bank
            from ui_evidence.scenario_bank.feature_export import persist_features_from_bank
            from ui_evidence.scenario_bank.quality import rate_invent_bank
            from ui_evidence.scenario_bank.repo import get_repo
            from ui_evidence.scenario_bank.scenario_planner import invent_for_service
            from ui_evidence.scenario_bank.spec_derive import derive_and_store
            from specs.openapi_tools.registry import list_tools
            from specs.catalog.openapi_sync import sync_openapi_for_service

            # Auto-sync OpenAPI when invent/feed starts — Specs uses this cache.
            knowledge["openapi_sync"] = sync_openapi_for_service(
                plugin.spt_service_id or service_key,
                env_n,
                force=True,
            )
            tools = list(
                (
                    list_tools(service=plugin.spt_service_id, limit=1000) or {}
                ).get("tools")
                or []
            )
            derive_and_store(service_key, env_n, tools)
            invent = invent_for_service(
                service_key,
                env_n,
                tools=tools,
                force_llm=force_llm,
            )
            llm_invoked = bool(invent.get("llm_invoked"))
            knowledge["invent_complete"] = bool(invent.get("invent_complete"))
            knowledge["needs_reinvent"] = False if invent.get("invent_complete") else (
                load_bank(service_key, env_n).get("needs_reinvent") or False
            )
            knowledge["llm_invoked"] = llm_invoked
            knowledge["invent_call_count"] = invent.get("call_count", 0)
            feats = persist_features_from_bank(service_key, env_n)
            knowledge["features_count"] = feats.get("count", 0)
            rating = rate_invent_bank(service_key, env_n)
            knowledge["quality_score"] = rating.get("quality_score")
            knowledge["quality_reasons"] = rating.get("quality_reasons")
            invent["quality"] = rating
            invent["features_count"] = feats.get("count", 0)
            get_repo().upsert_knowledge(service_key, env_n, knowledge)
            # optional debug mirror (not SoT)
            kpath.write_text(json.dumps(knowledge, indent=2), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            invent = {
                "ok": False,
                "skipped": False,
                "llm_invoked": False,
                "call_count": 0,
                "error": str(exc),
            }

    status = "ok"
    if not smoke.get("ok"):
        status = "onboard_blocked"
    elif prep.get("fail_closed") or (
        not prep.get("ok", True) and not prep.get("skipped")
    ):
        status = "prep_failed"

    invent_note = "onboard complete"
    if not smoke.get("ok"):
        invent_note = "seed-only; smoke blocked invent"
    elif invent.get("reason") == "litellm_unavailable":
        invent_note = "seed-only; LiteLLM unavailable — invent blocked (Phase 5 N/A live)"
    elif invent.get("reason") == "warm_invent_complete":
        invent_note = "warm path; invent skipped (zero LLM)"
    elif llm_invoked:
        invent_note = f"cold invent call_count={invent.get('call_count', 0)}"

    return {
        "ok": status == "ok" or (status == "onboard_blocked" and prep.get("ok", True)),
        "status": status,
        "plugin_id": plugin_id,
        "env": env_n,
        "contract_smoke": smoke,
        "prep": prep,
        "bank": bank,
        "invent": invent,
        "hash_drift": drift,
        "knowledge_path": str(kpath),
        "knowledge_backend": "repo",
        "quality": invent.get("quality"),
        "llm_invoked": llm_invoked,
        "litellm": {
            "available": litellm.get("available"),
            "model": litellm.get("model"),
            "models_count": litellm.get("models_count"),
            "base_url": litellm.get("base_url"),
            "error": litellm.get("error"),
        },
        "note": invent_note,
    }
