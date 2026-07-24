"""SPT-local overrides/custom UI flows & suites (JSON under data_dir)."""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any

from app.config import settings
from app.ui_flow_catalog import (
    DEFAULT_FLOW_IDS,
    RELEASE_GATE_PROFILES,
    SMOKE_SUITE_PROFILES,
    SUITE_META,
    UI_FLOW_META,
)

_LOCK = threading.Lock()
_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{1,63}$")
_BUILTIN_FLOW_IDS = frozenset(DEFAULT_FLOW_IDS) | frozenset(UI_FLOW_META.keys())
_BUILTIN_SUITE_IDS = frozenset(s["id"] for s in SUITE_META)


class UiCatalogError(ValueError):
    pass


def _path() -> Path:
    return Path(settings.data_dir) / "ui_catalog.json"


def _empty() -> dict[str, Any]:
    return {
        "version": 1,
        "flows": {},
        "flow_overrides": {},
        "suites": {},
        "suite_overrides": {},
    }


def load_store() -> dict[str, Any]:
    path = _path()
    if not path.is_file():
        return _empty()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty()
    if not isinstance(raw, dict):
        return _empty()
    out = _empty()
    for key in ("flows", "flow_overrides", "suites", "suite_overrides"):
        val = raw.get(key)
        if isinstance(val, dict):
            out[key] = {str(k): v for k, v in val.items() if isinstance(v, dict)}
    out["version"] = int(raw.get("version") or 1)
    return out


def save_store(data: dict[str, Any]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": int(data.get("version") or 1),
        "flows": data.get("flows") or {},
        "flow_overrides": data.get("flow_overrides") or {},
        "suites": data.get("suites") or {},
        "suite_overrides": data.get("suite_overrides") or {},
    }
    tmp = path.with_suffix(".json.tmp")
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    with _LOCK:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)


def known_agent_flow_ids(extra: list[str] | None = None) -> set[str]:
    ids = set(_BUILTIN_FLOW_IDS)
    if extra:
        ids.update(str(x) for x in extra if x)
    store = load_store()
    ids.update(store.get("flows") or {})
    return ids


def validate_id(fid: str, *, kind: str = "id") -> str:
    s = (fid or "").strip()
    if not _ID_RE.match(s):
        raise UiCatalogError(
            f"Invalid {kind} {fid!r}: use letters, numbers, underscore; start with a letter"
        )
    return s


def _clean_str_list(vals: Any) -> list[str]:
    if not isinstance(vals, list):
        return []
    out: list[str] = []
    for v in vals:
        t = str(v or "").strip()
        if t:
            out.append(t)
    return out


def upsert_flow(
    body: dict[str, Any],
    *,
    create: bool = False,
    deterministic: list[str] | None = None,
) -> dict[str, Any]:
    fid = validate_id(str(body.get("id") or ""), kind="flow id")
    agent_ids = known_agent_flow_ids(deterministic)
    # Agent executables = builtins + agent list (not custom SPT aliases)
    executable = set(_BUILTIN_FLOW_IDS)
    if deterministic:
        executable.update(str(x) for x in deterministic if x)

    store = load_store()
    customs = dict(store.get("flows") or {})
    overrides = dict(store.get("flow_overrides") or {})

    is_builtin = fid in _BUILTIN_FLOW_IDS or (fid in executable and fid not in customs)
    is_custom = fid in customs

    if create and (is_builtin or is_custom):
        raise UiCatalogError(f"Flow {fid!r} already exists")

    if is_builtin and not is_custom:
        # Metadata override only
        patch = {
            "label": str(body.get("label") or "").strip() or None,
            "group": str(body.get("group") or "").strip() or None,
            "summary": str(body.get("summary") or "").strip() or None,
            "steps": _clean_str_list(body.get("steps")),
            "verifications": _clean_str_list(body.get("verifications")),
        }
        clean = {k: v for k, v in patch.items() if v is not None and v != []}
        # Allow empty lists to clear steps/verifications
        if "steps" in body:
            clean["steps"] = _clean_str_list(body.get("steps"))
        if "verifications" in body:
            clean["verifications"] = _clean_str_list(body.get("verifications"))
        overrides[fid] = {**(overrides.get(fid) or {}), **clean}
        store["flow_overrides"] = overrides
        save_store(store)
        return {"id": fid, "custom": False, "override": True, **overrides[fid]}

    # Custom flow
    runs_as = str(body.get("runs_as") or "").strip()
    if not runs_as:
        if is_custom:
            runs_as = str((customs[fid] or {}).get("runs_as") or "")
        if not runs_as:
            raise UiCatalogError("runs_as is required for custom flows")
    if runs_as not in executable:
        raise UiCatalogError(
            f"runs_as {runs_as!r} is not a known agent profile. "
            f"Pick one of: {', '.join(sorted(executable)[:12])}…"
        )
    if create and fid in executable:
        raise UiCatalogError(f"Cannot create custom flow with builtin id {fid!r}")

    row = {
        "id": fid,
        "label": str(body.get("label") or fid).strip() or fid,
        "group": str(body.get("group") or "Custom").strip() or "Custom",
        "summary": str(body.get("summary") or "").strip(),
        "steps": _clean_str_list(body.get("steps")),
        "verifications": _clean_str_list(body.get("verifications")),
        "runs_as": runs_as,
    }
    if is_custom and not create:
        prev = customs[fid]
        if "label" not in body:
            row["label"] = prev.get("label") or row["label"]
        if "group" not in body:
            row["group"] = prev.get("group") or row["group"]
        if "summary" not in body:
            row["summary"] = prev.get("summary") or ""
        if "steps" not in body:
            row["steps"] = list(prev.get("steps") or [])
        if "verifications" not in body:
            row["verifications"] = list(prev.get("verifications") or [])
        if "runs_as" not in body:
            row["runs_as"] = prev.get("runs_as") or runs_as

    customs[fid] = row
    store["flows"] = customs
    save_store(store)
    return {**row, "custom": True}


def delete_flow(fid: str, *, reset: bool = False) -> dict[str, Any]:
    fid = validate_id(fid, kind="flow id")
    store = load_store()
    customs = dict(store.get("flows") or {})
    overrides = dict(store.get("flow_overrides") or {})

    if fid in customs:
        del customs[fid]
        store["flows"] = customs
        save_store(store)
        return {"deleted": fid, "custom": True}

    if reset and fid in overrides:
        del overrides[fid]
        store["flow_overrides"] = overrides
        save_store(store)
        return {"reset": fid, "custom": False}

    if fid in _BUILTIN_FLOW_IDS:
        raise UiCatalogError(
            f"Builtin flow {fid!r} cannot be deleted; use reset=1 to clear overrides"
        )
    raise UiCatalogError(f"Flow {fid!r} not found")


def upsert_suite(
    body: dict[str, Any],
    *,
    create: bool = False,
    deterministic: list[str] | None = None,
) -> dict[str, Any]:
    sid = validate_id(str(body.get("id") or ""), kind="suite id")
    store = load_store()
    customs = dict(store.get("suites") or {})
    overrides = dict(store.get("suite_overrides") or {})
    flow_ids = known_agent_flow_ids(deterministic)

    is_builtin = sid in _BUILTIN_SUITE_IDS
    is_custom = sid in customs

    if create and (is_builtin or is_custom):
        raise UiCatalogError(f"Suite {sid!r} already exists")

    profiles = _clean_str_list(body.get("profiles"))
    if "profiles" in body and not profiles:
        raise UiCatalogError("Suite profiles list cannot be empty")

    agent_suite = str(body.get("agent_suite") or "smoke").strip() or "smoke"
    if agent_suite not in ("smoke", "release_gate"):
        raise UiCatalogError("agent_suite must be smoke or release_gate")

    if profiles:
        unknown = [p for p in profiles if p not in flow_ids]
        if unknown:
            raise UiCatalogError(f"Unknown flow ids in suite: {', '.join(unknown)}")

    if is_builtin and not is_custom:
        patch: dict[str, Any] = {}
        if "label" in body:
            patch["label"] = str(body.get("label") or "").strip()
        if "summary" in body:
            patch["summary"] = str(body.get("summary") or "").strip()
        if "profiles" in body:
            patch["profiles"] = profiles
        if "agent_suite" in body:
            patch["agent_suite"] = agent_suite
        overrides[sid] = {**(overrides.get(sid) or {}), **patch}
        store["suite_overrides"] = overrides
        save_store(store)
        return {"id": sid, "custom": False, "override": True, **overrides[sid]}

    if create and is_builtin:
        raise UiCatalogError(f"Cannot create custom suite with builtin id {sid!r}")

    row = {
        "id": sid,
        "label": str(body.get("label") or sid).strip() or sid,
        "summary": str(body.get("summary") or "").strip(),
        "profiles": profiles
        or list((customs.get(sid) or {}).get("profiles") or [])
        or list(SMOKE_SUITE_PROFILES),
        "agent_suite": agent_suite,
    }
    if not row["profiles"]:
        raise UiCatalogError("Suite profiles list cannot be empty")
    if is_custom and not create:
        prev = customs[sid]
        if "label" not in body:
            row["label"] = prev.get("label") or row["label"]
        if "summary" not in body:
            row["summary"] = prev.get("summary") or ""
        if "profiles" not in body:
            row["profiles"] = list(prev.get("profiles") or [])
        if "agent_suite" not in body:
            row["agent_suite"] = prev.get("agent_suite") or "smoke"

    customs[sid] = row
    store["suites"] = customs
    save_store(store)
    return {**row, "custom": True}


def delete_suite(sid: str, *, reset: bool = False) -> dict[str, Any]:
    sid = validate_id(sid, kind="suite id")
    store = load_store()
    customs = dict(store.get("suites") or {})
    overrides = dict(store.get("suite_overrides") or {})

    if sid in customs:
        del customs[sid]
        store["suites"] = customs
        save_store(store)
        return {"deleted": sid, "custom": True}

    if reset and sid in overrides:
        del overrides[sid]
        store["suite_overrides"] = overrides
        save_store(store)
        return {"reset": sid, "custom": False}

    if sid in _BUILTIN_SUITE_IDS:
        raise UiCatalogError(
            f"Builtin suite {sid!r} cannot be deleted; use reset=1 to clear overrides"
        )
    raise UiCatalogError(f"Suite {sid!r} not found")


def merge_catalog(base: dict[str, Any]) -> dict[str, Any]:
    """Annotate + merge store into a catalog from build_ui_flow_catalog."""
    store = load_store()
    flow_overrides = store.get("flow_overrides") or {}
    suite_overrides = store.get("suite_overrides") or {}
    custom_flows = store.get("flows") or {}
    custom_suites = store.get("suites") or {}

    flows: list[dict[str, Any]] = []
    for f in base.get("flows") or []:
        fid = str(f.get("id") or "")
        ov = flow_overrides.get(fid) or {}
        row = dict(f)
        for key in ("label", "group", "summary", "steps", "verifications"):
            if key in ov and ov[key] is not None:
                row[key] = ov[key]
        row["custom"] = False
        row["editable"] = True
        row["deletable"] = False
        row["resettable"] = fid in flow_overrides
        row["runs_as"] = fid
        flows.append(row)

    seen = {str(f.get("id")) for f in flows}
    for fid, raw in custom_flows.items():
        if fid in seen:
            continue
        row = {
            "id": fid,
            "label": raw.get("label") or fid,
            "group": raw.get("group") or "Custom",
            "summary": raw.get("summary") or "",
            "steps": list(raw.get("steps") or []),
            "verifications": list(raw.get("verifications") or []),
            "runs_as": raw.get("runs_as") or fid,
            "custom": True,
            "editable": True,
            "deletable": True,
            "resettable": False,
        }
        flows.append(row)
        seen.add(fid)

    suites: list[dict[str, Any]] = []
    for s in base.get("suites") or []:
        sid = str(s.get("id") or "")
        ov = suite_overrides.get(sid) or {}
        row = dict(s)
        for key in ("label", "summary", "profiles", "agent_suite"):
            if key in ov and ov[key] is not None:
                row[key] = ov[key]
        row.setdefault("agent_suite", sid if sid in ("smoke", "release_gate") else "smoke")
        row["custom"] = False
        row["editable"] = True
        row["deletable"] = False
        row["resettable"] = sid in suite_overrides
        suites.append(row)

    seen_s = {str(s.get("id")) for s in suites}
    for sid, raw in custom_suites.items():
        if sid in seen_s:
            continue
        suites.append(
            {
                "id": sid,
                "label": raw.get("label") or sid,
                "summary": raw.get("summary") or "",
                "profiles": list(raw.get("profiles") or []),
                "agent_suite": raw.get("agent_suite") or "smoke",
                "custom": True,
                "editable": True,
                "deletable": True,
                "resettable": False,
            }
        )

    out = dict(base)
    out["flows"] = flows
    out["suites"] = suites
    return out


def _flow_runs_as(fid: str, store: dict[str, Any] | None = None) -> str:
    store = store or load_store()
    custom = (store.get("flows") or {}).get(fid)
    if custom and custom.get("runs_as"):
        return str(custom["runs_as"])
    return fid


def resolve_ui_run(cfg: dict[str, Any]) -> dict[str, Any]:
    """Map SPT catalog ids → agent-executable ui_profile / ui_suite / ui_profiles."""
    out = dict(cfg)
    store = load_store()
    ui_suite = out.get("ui_suite")
    ui_profile = out.get("ui_profile")

    if ui_suite:
        sid = str(ui_suite)
        suite_row: dict[str, Any] | None = None
        custom = (store.get("suites") or {}).get(sid)
        if custom:
            suite_row = custom
        else:
            for s in SUITE_META:
                if s["id"] == sid:
                    suite_row = dict(s)
                    break
            ov = (store.get("suite_overrides") or {}).get(sid) or {}
            if suite_row is not None and ov:
                suite_row = {**suite_row, **ov}
            elif suite_row is None and ov:
                suite_row = {"id": sid, **ov}

        if suite_row is None:
            # Unknown suite — leave as-is (agent may reject)
            return out

        profiles = list(suite_row.get("profiles") or [])
        if not profiles:
            if sid == "smoke":
                profiles = list(SMOKE_SUITE_PROFILES)
            elif sid == "release_gate":
                profiles = list(RELEASE_GATE_PROFILES)

        resolved = [_flow_runs_as(p, store) for p in profiles]
        agent_suite = str(suite_row.get("agent_suite") or "")
        if agent_suite not in ("smoke", "release_gate"):
            agent_suite = sid if sid in ("smoke", "release_gate") else "smoke"

        out["ui_suite_requested"] = sid
        out["ui_suite"] = agent_suite
        out["ui_profiles"] = resolved
        out["ui_profile"] = None
        return out

    if ui_profile:
        fid = str(ui_profile)
        out["ui_profile_requested"] = fid
        out["ui_profile"] = _flow_runs_as(fid, store)
        out["ui_profiles"] = None
    return out
