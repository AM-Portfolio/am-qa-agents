"""Discover and load am.qa.plugin/v1 manifests from qa-agent/plugins/."""
from __future__ import annotations

import importlib.util
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)

_API_VERSION = "am.qa.plugin/v1"
_CACHE: dict[str, "Plugin"] | None = None


def plugins_root() -> Path:
    """qa-agent/plugins (sibling of ui_evidence)."""
    return Path(__file__).resolve().parents[2] / "plugins"


@dataclass
class Plugin:
    id: str
    root: Path
    manifest: dict[str, Any]
    enabled: bool = True

    @property
    def suite(self) -> str:
        return str(self.manifest.get("suite") or "")

    @property
    def api_pack(self) -> str:
        return str(self.manifest.get("api_pack") or "")

    @property
    def spt_service_id(self) -> str:
        return str(self.manifest.get("spt_service_id") or self.id)

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.manifest.get("title"),
            "enabled": self.enabled,
            "suite": self.suite,
            "api_pack": self.api_pack,
            "spt_service_id": self.spt_service_id,
            "depends_on": list(self.manifest.get("depends_on") or []),
            "portal": self.manifest.get("portal") or {},
            "env_policy": self.manifest.get("env_policy") or {},
            "root": str(self.root),
        }


def _state_path(plugin_dir: Path) -> Path:
    return plugin_dir / "plugin.state.yaml"


def _effective_enabled(manifest: dict[str, Any], plugin_dir: Path) -> bool:
    base = bool(manifest.get("enabled", True))
    state_file = _state_path(plugin_dir)
    if not state_file.is_file():
        return base
    try:
        state = yaml.safe_load(state_file.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return base
    if "enabled" in state:
        return bool(state["enabled"])
    return base


def _validate_manifest(data: dict[str, Any], path: Path) -> None:
    if not isinstance(data, dict):
        raise ValueError(f"plugin manifest not a mapping: {path}")
    if data.get("apiVersion") != _API_VERSION:
        raise ValueError(
            f"unsupported apiVersion {data.get('apiVersion')!r} in {path} "
            f"(want {_API_VERSION})"
        )
    for key in ("id", "suite", "api_pack", "spt_service_id"):
        if not str(data.get(key) or "").strip():
            raise ValueError(f"plugin {path} missing required field {key}")


def _scan(root: Path | None = None) -> dict[str, Plugin]:
    root = root or plugins_root()
    found: dict[str, Plugin] = {}
    if not root.is_dir():
        logger.debug("plugins root missing: %s", root)
        return found
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith((".", "_")):
            continue
        manifest_path = child / "plugin.yaml"
        if not manifest_path.is_file():
            continue
        try:
            data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
            _validate_manifest(data, manifest_path)
            pid = str(data["id"])
            enabled = _effective_enabled(data, child)
            found[pid] = Plugin(
                id=pid, root=child, manifest=data, enabled=enabled
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("skip plugin %s: %s", child.name, exc)
    return found


def reload_plugins(*, root: Path | None = None) -> dict[str, Any]:
    global _CACHE
    _CACHE = _scan(root)
    return {
        "ok": True,
        "count": len(_CACHE),
        "enabled": sum(1 for p in _CACHE.values() if p.enabled),
        "ids": sorted(_CACHE.keys()),
    }


def _cache() -> dict[str, Plugin]:
    global _CACHE
    if _CACHE is None:
        _CACHE = _scan()
    return _CACHE


def list_plugins(*, include_disabled: bool = False) -> list[dict[str, Any]]:
    rows = []
    for p in sorted(_cache().values(), key=lambda x: x.id):
        if not include_disabled and not p.enabled:
            continue
        rows.append(p.summary())
    return rows


def get_plugin(
    *,
    plugin_id: str | None = None,
    suite: str | None = None,
    api_pack: str | None = None,
    include_disabled: bool = False,
) -> Plugin | None:
    for p in _cache().values():
        if not include_disabled and not p.enabled:
            continue
        if plugin_id and p.id == plugin_id:
            return p
        if suite and p.suite == suite:
            return p
        if api_pack and p.api_pack == api_pack:
            return p
    return None


def resolve_api_pack_default(suite: str) -> str:
    """Gateway/ops: suite → api_pack from enabled plugin, else empty."""
    p = get_plugin(suite=suite)
    return p.api_pack if p else ""


def set_plugin_enabled(plugin_id: str, enabled: bool) -> dict[str, Any]:
    p = get_plugin(plugin_id=plugin_id, include_disabled=True)
    if p is None:
        return {"ok": False, "error": "not_found", "id": plugin_id}
    state_file = _state_path(p.root)
    state_file.write_text(
        yaml.safe_dump({"enabled": bool(enabled)}, sort_keys=False),
        encoding="utf-8",
    )
    reload_plugins()
    again = get_plugin(plugin_id=plugin_id, include_disabled=True)
    return {
        "ok": True,
        "id": plugin_id,
        "enabled": bool(again.enabled) if again else bool(enabled),
        "state_file": str(state_file),
    }


def load_yaml_rel(plugin: Plugin, rel: str | None) -> Any:
    if not rel:
        return None
    path = (plugin.root / rel).resolve()
    if not str(path).startswith(str(plugin.root.resolve())):
        raise ValueError(f"catalog path escapes plugin root: {rel}")
    if not path.is_file():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_api_catalog(plugin: Plugin) -> dict[str, Any]:
    cat = (plugin.manifest.get("catalog") or {}).get("apis")
    data = load_yaml_rel(plugin, cat)
    return data if isinstance(data, dict) else {"flows": data or []}


def load_ui_profiles(plugin: Plugin) -> list[str]:
    cat = (plugin.manifest.get("catalog") or {}).get("ui_profiles")
    data = load_yaml_rel(plugin, cat)
    if isinstance(data, dict):
        profiles = data.get("profiles") or data.get("ui_profiles") or []
        return [str(x) for x in profiles]
    if isinstance(data, list):
        return [str(x) for x in data]
    return []


def load_feature_ids(plugin: Plugin) -> list[str]:
    feat_rel = (plugin.manifest.get("catalog") or {}).get("features")
    if not feat_rel:
        return []
    feat_dir = (plugin.root / feat_rel).resolve()
    if not feat_dir.is_dir():
        return []
    return sorted(p.name for p in feat_dir.glob("*.feature"))


def catalog_bundle(plugin: Plugin) -> dict[str, Any]:
    return {
        "id": plugin.id,
        "apis": load_api_catalog(plugin),
        "ui_profiles": load_ui_profiles(plugin),
        "features": load_feature_ids(plugin),
        "runners": plugin.manifest.get("runners") or {},
        "reports": plugin.manifest.get("reports") or {},
    }


def import_entry(plugin: Plugin, entry: str) -> Any:
    """Load module:callable from plugin dir (e.g. seed:prepare)."""
    if ":" not in entry:
        raise ValueError(f"entry must be module:callable, got {entry!r}")
    mod_name, func_name = entry.split(":", 1)
    mod_path = plugin.root / f"{mod_name}.py"
    if not mod_path.is_file():
        raise FileNotFoundError(f"plugin entry module missing: {mod_path}")
    spec = importlib.util.spec_from_file_location(
        f"qa_plugin_{plugin.id}_{mod_name}", mod_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {mod_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = getattr(module, func_name, None)
    if fn is None:
        raise AttributeError(f"{mod_path} has no {func_name}")
    return fn


def run_data_prep(
    plugin: Plugin,
    env: str,
    ctx: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    prep = plugin.manifest.get("data_prep") or {}
    entry = prep.get("entry")
    if not entry:
        return {"ok": True, "skipped": True, "reason": "no_data_prep"}
    env_n = (env or "dev").strip().lower()
    if env_n == "dig":
        env_n = "dev"
    fail_closed = {str(x).lower() for x in (prep.get("fail_closed_envs") or [])}
    assert_only = {str(x).lower() for x in (prep.get("assert_only_envs") or [])}
    fn = import_entry(plugin, str(entry))
    result = fn(env=env_n, ctx=ctx or {}, assert_only=env_n in assert_only)
    if not isinstance(result, dict):
        result = {"ok": bool(result), "raw": result}
    if env_n in fail_closed and not result.get("ok", True):
        result["fail_closed"] = True
    return result


def portal_defaults_for_suite(suite: str) -> dict[str, Any]:
    p = get_plugin(suite=suite)
    if not p:
        return {}
    portal = p.manifest.get("portal") or {}
    ops = portal.get("ops_start_defaults") or portal
    return {
        "suite": ops.get("suite") or p.suite,
        "api_pack": ops.get("api_pack") or p.api_pack,
        "default_env": ops.get("default_env") or "dev",
        "skip_soak": bool(ops.get("skip_soak", True)),
    }
