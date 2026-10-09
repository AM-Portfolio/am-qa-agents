"""Locate / load am-specs dataset packs for import."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from specs.data_gen.constants import SUITE_TO_PROFILE


def disk_profile_for_suite(suite_or_profile: str) -> str:
    key = (suite_or_profile or "default").strip().lower()
    return SUITE_TO_PROFILE.get(key, key)


def datasets_root() -> Path | None:
    raw = (os.environ.get("AM_SPECS_DATASETS_PATH") or "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_dir() else None
    return None


def profile_pack_dir(service: str, profile: str, *, root: Path | None = None) -> Path | None:
    base = root or datasets_root()
    if base is None:
        return None
    # Layout: <root>/<service>/v1/profiles/<profile>/  OR <root>/datasets/<service>/...
    candidates = [
        base / service / "v1" / "profiles" / profile,
        base / "datasets" / service / "v1" / "profiles" / profile,
        base / ".generated" / "datasets" / service / "v1" / "profiles" / profile,
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return None


def load_var_defaults(service: str, environment: str, *, root: Path | None = None) -> dict[str, str]:
    base = root or datasets_root()
    if base is None:
        return {}
    env = "dev" if environment == "dig" else environment
    for rel in (
        Path(service) / "v1" / "envs" / env / "var_defaults.json",
        Path("datasets") / service / "v1" / "envs" / env / "var_defaults.json",
        Path(".generated") / "datasets" / service / "v1" / "envs" / env / "var_defaults.json",
    ):
        path = base / rel
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                # nested var_defaults key or flat
                vd = data.get("var_defaults") if isinstance(data.get("var_defaults"), dict) else data
                return {
                    str(k): "" if v is None else str(v)
                    for k, v in vd.items()
                    if not str(k).startswith("_")
                }
    return {}


def load_examples_from_pack_dir(pack_dir: Path) -> list[dict[str, Any]]:
    """Read apis/**/*.json examples (skip README)."""
    apis_root = pack_dir / "apis"
    if not apis_root.is_dir():
        # flat legacy
        apis_root = pack_dir
    out: list[dict[str, Any]] = []
    for path in sorted(apis_root.rglob("*.json")):
        if path.name.upper().startswith("README"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and (data.get("request") or data.get("path") or data.get("api_id")):
            # infer case_kind from parent folder when missing
            meta = dict(data.get("meta") or {}) if isinstance(data.get("meta"), dict) else {}
            if not meta.get("case_kind"):
                parent = path.parent.name
                if parent and parent not in {"apis", "by_api"}:
                    meta["case_kind"] = parent
                    data["meta"] = meta
            out.append(data)
    return out


def build_payload_set_doc(
    service: str,
    *,
    profile: str,
    examples: list[dict[str, Any]] | None = None,
    pack_dir: Path | None = None,
    env: dict[str, str] | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    from specs.data_gen.prefer import collapse_by_api_id

    rows = examples
    if rows is None and pack_dir is not None:
        rows = load_examples_from_pack_dir(pack_dir)
    rows = rows or []
    collapsed = collapse_by_api_id(rows)
    return {
        "service": service,
        "label": label or f"data-gen-{profile}",
        "apis": collapsed,
        "env": dict(env or {}),
        "source": {"kind": "am-specs-datasets", "profile": profile},
    }


def resolve_import_document(
    *,
    service: str,
    profile: str,
    body: dict[str, Any] | None = None,
    pack_path: str | Path | None = None,
    environment: str = "dev",
) -> dict[str, Any]:
    """Priority: body payload_set/collection → pack_path → AM_SPECS_DATASETS_PATH."""
    if body:
        if isinstance(body.get("payload_set"), dict):
            doc = dict(body["payload_set"])
            doc.setdefault("service", service)
            return {
                "format": "am-specs-dataset",
                "service": service,
                "profile": profile,
                "payload_set": doc,
                "label": body.get("label") or doc.get("label") or f"data-gen-{profile}",
                "env": body.get("env") or doc.get("env"),
            }
        if isinstance(body.get("collection"), dict):
            return {
                "format": body.get("format") or "am-specs-dataset",
                "service": service,
                "profile": profile,
                "payload_set": body["collection"],
                "label": body.get("label"),
                "env": body.get("environment") or body.get("env"),
            }
        if isinstance(body.get("apis"), dict) or isinstance(body.get("examples"), list):
            return {
                "format": "am-specs-dataset",
                "service": service,
                "profile": profile,
                "payload_set": body,
                "label": body.get("label") or f"data-gen-{profile}",
                "env": body.get("env"),
            }

    path = Path(pack_path) if pack_path else None
    if path and path.is_file() and path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return resolve_import_document(
            service=service, profile=profile, body=data if isinstance(data, dict) else None
        )
    if path and path.is_dir():
        env = load_var_defaults(service, environment)
        doc = build_payload_set_doc(service, profile=profile, pack_dir=path, env=env)
        return {
            "format": "am-specs-dataset",
            "service": service,
            "profile": profile,
            "payload_set": doc,
            "label": doc["label"],
            "env": env,
        }

    disk_prof = disk_profile_for_suite(profile)
    pack_dir = profile_pack_dir(service, disk_prof)
    if pack_dir is None and disk_prof == "prod":
        pack_dir = profile_pack_dir(service, "default")
    if pack_dir is None:
        raise FileNotFoundError(
            f"No data-gen pack for {service!r} profile={disk_prof!r}. "
            "Pass payload_set body, pack_path, or set AM_SPECS_DATASETS_PATH."
        )
    env = load_var_defaults(service, environment)
    doc = build_payload_set_doc(service, profile=disk_prof, pack_dir=pack_dir, env=env)
    return {
        "format": "am-specs-dataset",
        "service": service,
        "profile": disk_prof,
        "payload_set": doc,
        "label": doc["label"],
        "env": env,
        "pack_dir": str(pack_dir),
    }
