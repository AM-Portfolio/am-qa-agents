"""Chunked LiteLLM invent + OpenAPI grounding (Phase 5). Max 2 LLM calls."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from ui_evidence.scenario_bank.bank_store import (
    acquire_invent_lock,
    list_scenarios,
    load_bank,
    release_invent_lock,
    set_flags,
    upsert_scenario,
)
from ui_evidence.scenario_bank.invent_context import (
    build_invent_pack,
    path_is_banned,
    path_sequence_fingerprint,
    render_chunk_user,
)

logger = logging.getLogger(__name__)

MAX_INVENT_CALLS = 2
ChatFn = Callable[[str, str], str]
_STRICT_NEGATIVE_SKILLS = frozenset({"validation", "security", "level5_abuse"})


def _skills_path() -> Path:
    return Path(__file__).resolve().parent / "skills.yaml"


def load_invent_skill_ids() -> list[str]:
    """Skills to invent (exclude hand-seeded data_generator)."""
    data = yaml.safe_load(_skills_path().read_text(encoding="utf-8")) or {}
    out: list[str] = []
    for row in data.get("skills") or []:
        sid = str(row.get("id") or "")
        if sid and sid != "data_generator":
            out.append(sid)
    return out


def _chunk(items: list[str], n: int) -> list[list[str]]:
    if n <= 0:
        return [items]
    size = max(1, (len(items) + n - 1) // n)
    return [items[i : i + size] for i in range(0, len(items), size)][:n]


def _extract_json_array(text: str) -> list[Any]:
    text = (text or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict) and isinstance(parsed.get("scenarios"), list):
            return parsed["scenarios"]
    except json.JSONDecodeError:
        pass
    match = re.search(r"\[[\s\S]*\]", text)
    if not match:
        return []
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def _normalize_steps(steps: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for st in steps or []:
        if not isinstance(st, dict):
            continue
        step = dict(st)
        if "expected_status" in step and step["expected_status"] is not None:
            try:
                step["expected_status"] = int(step["expected_status"])
            except (TypeError, ValueError):
                pass
        out.append(step)
    return out


def ground_row(
    row: dict[str, Any],
    *,
    tool_paths: set[str],
    tool_names: set[str],
    ban_patterns: Optional[list[re.Pattern[str]]] = None,
) -> dict[str, Any]:
    """Mark ungrounded / incomplete invent rows draft; LLM UI → draft_ui."""
    out = dict(row)
    kind = str(out.get("kind") or "api").lower()
    if kind == "ui":
        out["status"] = "draft_ui"
        out["grounded"] = False
        return out

    steps = _normalize_steps(out.get("steps"))
    out["steps"] = steps
    if not steps:
        out["status"] = "draft"
        out["grounded"] = False
        out["ground_reason"] = "no_steps"
        return out

    skill = str(out.get("skill") or "")
    reasons: list[str] = []
    grounded = True
    patterns = ban_patterns or []

    for step in steps:
        tool = str(step.get("tool") or "").strip()
        path = str(step.get("path") or step.get("operation_path") or "").strip()
        path_l = path.lower()
        if path_is_banned(path, patterns):
            grounded = False
            reasons.append("banned_path")
            break
        if "expected_status" not in step or step.get("expected_status") is None:
            grounded = False
            reasons.append("missing_expected_status")
            break
        if tool and tool in tool_names:
            continue
        if path_l and any(path_l in p or p in path_l for p in tool_paths):
            continue
        grounded = False
        reasons.append("ungrounded_path")
        break

    if skill in _STRICT_NEGATIVE_SKILLS:
        if not out.get("negative"):
            grounded = False
            reasons.append("negative_required")
        # asserting step should be non-2xx
        statuses = [
            int(s["expected_status"])
            for s in steps
            if isinstance(s.get("expected_status"), int)
        ]
        if statuses and all(200 <= s < 300 for s in statuses):
            grounded = False
            reasons.append("negative_needs_non_2xx")

    out["grounded"] = grounded
    out["status"] = "runnable" if grounded else "draft"
    if reasons:
        out["ground_reason"] = ",".join(dict.fromkeys(reasons))
    return out


def _default_chat(system: str, user: str) -> str:
    import asyncio

    from ui_evidence.config import settings
    from ui_evidence.llm.factory import create_llm_client

    client = create_llm_client()
    model = settings.LLM_PLANNER_MODEL

    async def _run() -> str:
        return await client.chat_text(
            system=system,
            user=user,
            model=str(model),
            session_id="scenario-bank-invent",
            test_id="invent",
        )

    return asyncio.run(_run())


def invent_for_service(
    service_key: str,
    env: str,
    *,
    tools: list[dict[str, Any]],
    force_llm: bool = False,
    chat_fn: Optional[ChatFn] = None,
    owner: str = "",
    extra_context: str = "",
    scenarios_per_skill: int = 2,
    plugin_root: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Cold invent into bank. Caller must ensure LLM available + tools digest.
    Uses invent lock; max MAX_INVENT_CALLS chunked LLM calls.
    Prompts load from typed registry type=invent (not hardcoded).
    """
    env_n = "dev" if (env or "").lower() == "dig" else (env or "dev").lower()
    bank = load_bank(service_key, env_n)
    if (
        bank.get("invent_complete")
        and not bank.get("needs_reinvent")
        and not force_llm
    ):
        return {
            "ok": True,
            "skipped": True,
            "reason": "warm_invent_complete",
            "llm_invoked": False,
            "call_count": 0,
            "invent_complete": True,
        }

    lock = acquire_invent_lock(service_key, env_n, owner=owner or "invent")
    if not lock.get("ok"):
        return {
            "ok": False,
            "skipped": True,
            "reason": "lock_held",
            "llm_invoked": False,
            "call_count": 0,
            "lock": lock,
        }

    tool_paths = {
        str(t.get("path") or t.get("operation_path") or "").lower()
        for t in tools
        if t.get("path") or t.get("operation_path")
    }
    tool_names = {str(t.get("name") or "") for t in tools if t.get("name")}
    per_skill = max(1, min(int(scenarios_per_skill or 1), 3))

    skills = load_invent_skill_ids()
    # Ensure DB has derived surface + invent profile for this service
    try:
        from ui_evidence.scenario_bank.spec_derive import derive_and_store

        derive_and_store(service_key, env_n, tools)
    except Exception as exc:  # noqa: BLE001
        logger.warning("spec_derive failed (continuing): %s", exc)

    existing = list_scenarios(service_key, env_n)
    pack = build_invent_pack(
        service_key,
        env_n,
        tools=tools,
        skill_ids=skills,
        existing_scenarios=existing,
        plugin_root=plugin_root,
        scenarios_per_skill=per_skill,
    )
    # Optional thin extra_context append (domain notes) — keep short
    ctx = (extra_context or "").strip()
    if ctx:
        if len(ctx) > 2000:
            ctx = ctx[:2000] + "\n...[truncated]"
        pack["catalog_text"] = (
            str(pack.get("catalog_text") or "") + "\n\ndomain_notes:\n" + ctx
        )

    max_calls = min(MAX_INVENT_CALLS, int(pack["bundle"].max_invent_calls))
    chunks = _chunk(skills, max_calls)
    chat = chat_fn or _default_chat
    call_count = 0
    upserted = 0
    errors: list[str] = []
    seen_fps: set[str] = set()
    ban_pats = list(pack.get("ban_patterns") or [])
    system = str(pack["system"])

    try:
        for chunk in chunks:
            user = render_chunk_user(
                pack,
                service_key=service_key,
                env=env_n,
                chunk_skills=chunk,
                scenarios_per_skill=per_skill,
            )
            try:
                raw = chat(system, user)
                call_count += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))
                logger.warning("invent chat failed: %s", exc)
                break

            for item in _extract_json_array(raw):
                if not isinstance(item, dict):
                    continue
                skill = str(item.get("skill") or "")
                if skill not in chunk:
                    continue
                steps = _normalize_steps(item.get("steps"))
                fp = path_sequence_fingerprint(steps)
                if fp and fp in seen_fps:
                    continue
                if fp:
                    seen_fps.add(fp)
                dedupe = str(item.get("dedupe_key") or "").strip()
                if not dedupe:
                    slug = "".join(
                        c if c.isalnum() else "-"
                        for c in str(item.get("title") or skill).lower()
                    )[:40]
                    dedupe = f"invent:{skill}:{slug or 'case'}"
                auth = str(item.get("auth") or "user_jwt").strip() or "user_jwt"
                negative = bool(item.get("negative"))
                if skill in _STRICT_NEGATIVE_SKILLS:
                    negative = True
                row = ground_row(
                    {
                        "skill": skill,
                        "kind": item.get("kind") or "api",
                        "title": item.get("title") or skill,
                        "steps": steps,
                        "auth": auth,
                        "negative": negative,
                        "seed": False,
                        "dedupe_key": dedupe,
                        "llm_invented": True,
                        "schema_version": pack.get("schema_version"),
                    },
                    tool_paths=tool_paths,
                    tool_names=tool_names,
                    ban_patterns=ban_pats,
                )
                upsert_scenario(service_key, env_n, row)
                upserted += 1

        complete = call_count > 0 and not errors
        if complete:
            set_flags(
                service_key,
                env_n,
                invent_complete=True,
                needs_reinvent=False,
            )
        return {
            "ok": complete or upserted > 0,
            "skipped": False,
            "llm_invoked": call_count > 0,
            "call_count": call_count,
            "upserted": upserted,
            "invent_complete": complete,
            "errors": errors,
            "chunks": len(chunks),
            "prompt_type": "invent",
            "schema_version": pack.get("schema_version"),
            "provider_note": "chat_fn or LiteLLMClient",
        }
    finally:
        release_invent_lock(service_key, env_n, owner=str(lock.get("owner") or ""))
