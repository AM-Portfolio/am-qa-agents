"""Generic API pack runner driven by enabled QA plugins + scenario bank (Phase 7)."""
from __future__ import annotations

import importlib
import logging
from typing import Any, Callable, Optional

from ui_evidence.plugins.loader import get_plugin, run_data_prep

logger = logging.getLogger(__name__)

ExecuteFn = Callable[[str, str], dict[str, Any]]


def _import_dotted(path: str) -> Any:
    """Import module:attr or module.attr style entry."""
    if ":" in path:
        mod_name, attr = path.split(":", 1)
    else:
        mod_name, attr = path.rsplit(".", 1)
    mod = importlib.import_module(mod_name)
    return getattr(mod, attr)


def _normalize_env(env: str) -> str:
    e = (env or "dev").strip().lower()
    return "dev" if e == "dig" else e


def _execute_api_pack(plugin: Any, env_n: str) -> dict[str, Any]:
    runners = plugin.manifest.get("runners") or {}
    flows_entry = runners.get("api_flows")
    sweep_services = list(
        runners.get("api_sweep_services") or [plugin.spt_service_id]
    )
    if not flows_entry:
        return {
            "api_pack": plugin.api_pack,
            "plugin_id": plugin.id,
            "decision": "NO_GO",
            "error": "plugin.runners.api_flows missing",
        }

    run_flows = _import_dotted(str(flows_entry))
    flows = run_flows(environment=env_n, refresh=True)

    sweep: dict[str, Any] = {}
    try:
        from ui_evidence.api.run_all_auth_user_apis import run_all_auth_user_apis

        sweep = run_all_auth_user_apis(
            environment=env_n, services=sweep_services, refresh=True
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("api_pack sweep failed plugin=%s err=%s", plugin.id, exc)
        sweep = {"decision": "NO_GO", "error": str(exc)}

    decision = (
        "GO"
        if flows.get("decision") == "GO" and sweep.get("decision") == "GO"
        else "NO_GO"
    )
    return {
        "api_pack": plugin.api_pack,
        "plugin_id": plugin.id,
        "decision": decision,
        "api_flows": {
            "decision": flows.get("decision"),
            "counts": flows.get("counts"),
            "flows": flows.get("flows"),
            "report_html": flows.get("report_html"),
            "report_json": flows.get("report_json"),
        },
        "api_sweep": {
            "decision": sweep.get("decision"),
            "counts": sweep.get("counts"),
            "report_html": sweep.get("report_html"),
            "report_json": sweep.get("report_json"),
            "issues": sweep.get("issues"),
            "error": sweep.get("error"),
        },
    }


def bank_advisory(service_key: str, env: str) -> dict[str, Any]:
    """Select-few + coverage / draft_ui backlog for report."""
    from ui_evidence.scenario_bank.bank_store import list_scenarios, load_bank
    from ui_evidence.scenario_bank.env_policy import select_few

    bank = load_bank(service_key, env)
    rows = list(bank.get("scenarios") or list_scenarios(service_key, env))
    selected = select_few(rows, env)
    draft_ui = [r for r in rows if str(r.get("status")) == "draft_ui"]
    draft = [r for r in rows if str(r.get("status")) == "draft"]
    runnable = [r for r in rows if str(r.get("status")) == "runnable"]
    return {
        "service_key": service_key,
        "env": selected.get("env"),
        "invent_complete": bool(bank.get("invent_complete")),
        "needs_reinvent": bool(bank.get("needs_reinvent")),
        "bank_count": len(rows),
        "runnable_count": len(runnable),
        "draft_count": len(draft),
        "draft_ui_backlog": [
            {"skill": r.get("skill"), "dedupe_key": r.get("dedupe_key")}
            for r in draft_ui
        ],
        "select_few": selected.get("select_few") or [],
        "select_few_count": selected.get("select_few_count"),
        "skipped": [
            {"skill": r.get("skill"), "skip_reason": r.get("skip_reason")}
            for r in (selected.get("skipped") or [])
        ],
        "coverage_advisory": {
            "bank_total": len(rows),
            "selected": selected.get("select_few_count"),
            "note": "pack GO/NO_GO is selected runnable execute; bank coverage is advisory",
        },
    }


def run_api_pack(
    api_pack: str,
    env: str,
    *,
    skip_prep: bool = False,
    execute_fn: Optional[ExecuteFn] = None,
) -> dict[str, Any]:
    """
    Select-few advisory → data_prep (fail-closed on env=dev) → execute API pack.
    Never silent SKIPPED green: empty pack / missing plugin → NO_GO.
    """
    pack = (api_pack or "").strip()
    if not pack:
        return {
            "api_pack": "",
            "decision": "NO_GO",
            "reason": "empty_api_pack",
            "llm_invoked": False,
        }

    plugin = get_plugin(api_pack=pack)
    if plugin is None:
        return {
            "api_pack": pack,
            "decision": "NO_GO",
            "error": f"no enabled plugin for api_pack={pack!r}",
            "llm_invoked": False,
        }

    env_n = _normalize_env(env)
    service_key = str(
        (plugin.manifest.get("scenario_bank") or {}).get("service_key", plugin.id)
    )
    bank = bank_advisory(service_key, env_n)

    prep: dict[str, Any] = {"ok": True, "skipped": True}
    if not skip_prep:
        try:
            prep = run_data_prep(plugin, env_n, ctx={"bank": bank})
        except Exception as exc:  # noqa: BLE001
            prep = {"ok": False, "error": str(exc)}

    fail_closed = bool(prep.get("fail_closed")) or (
        env_n
        in {
            str(x).lower()
            for x in (
                (plugin.manifest.get("data_prep") or {}).get("fail_closed_envs") or []
            )
        }
        and not prep.get("ok", True)
        and not prep.get("skipped")
    )

    if fail_closed and not prep.get("ok", True):
        return {
            "api_pack": pack,
            "plugin_id": plugin.id,
            "env": env_n,
            "decision": "NO_GO",
            "reason": "prep_fail_closed",
            "prep": prep,
            "bank": bank,
            "executed": False,
            "llm_invoked": False,
            "smoke": None,
            "api_flows": {},
            "api_sweep": {},
        }

    if execute_fn is not None:
        executed = execute_fn(pack, env_n)
    else:
        executed = _execute_api_pack(plugin, env_n)

    decision = str(executed.get("decision") or "NO_GO")
    if decision == "SKIPPED":
        # Refuse silent green skip
        decision = "NO_GO"
        executed = {**executed, "decision": "NO_GO", "reason": "refused_silent_skip"}

    return {
        **executed,
        "api_pack": pack,
        "plugin_id": plugin.id,
        "env": env_n,
        "decision": decision,
        "prep": prep,
        "bank": bank,
        "executed": True,
        "llm_invoked": False,
    }
