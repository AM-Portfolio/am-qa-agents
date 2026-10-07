"""QA service plugins — discoverable manifests under qa-agent/plugins/."""

from ui_evidence.plugins.loader import (
    get_plugin,
    list_plugins,
    plugins_root,
    reload_plugins,
    resolve_api_pack_default,
    set_plugin_enabled,
)
from ui_evidence.plugins.onboard import onboard_plugin
from ui_evidence.plugins.pack_runner import run_api_pack

__all__ = [
    "get_plugin",
    "list_plugins",
    "onboard_plugin",
    "plugins_root",
    "reload_plugins",
    "resolve_api_pack_default",
    "run_api_pack",
    "set_plugin_enabled",
]
