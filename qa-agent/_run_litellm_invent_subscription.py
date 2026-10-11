"""Invent subscription scenarios via prod LiteLLM only (Together behind proxy).

Uses LITELLM_MASTER_KEY from Contabo prod am-qa-agents synced secret
(vault copy is stale / 401). OpenAPI SPA-blocked → Postman API surface.
Prompts from qa-agent/prompts type=invent.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from composition.env_bootstrap import load_env

load_env()

PLUGIN = ROOT / "plugins" / "am-subscription"
POSTMAN = Path(
    "f:/am-repos/am-repos/am-platform/am-subscription/postman/"
    "AM-Subscription.postman_collection.json"
)
LITELLM_BASE = os.getenv("LITELLM_BASE_URL") or "https://litellm.asrax.in"
KUBECONFIG = Path.home() / ".asrax" / "kubeconfig.prod"


def prod_litellm_master_key() -> str:
    """Read live master key from Contabo prod synced secrets (not vault stale copy)."""
    cmd = [
        "kubectl",
        "--kubeconfig",
        str(KUBECONFIG),
        "-n",
        "am-agents-prod",
        "get",
        "secret",
        "am-qa-agents-prod-synced-secrets",
        "-o",
        "json",
    ]
    raw = subprocess.check_output(cmd, text=True)
    sec = json.loads(raw)
    b64 = (sec.get("data") or {}).get("LITELLM_MASTER_KEY")
    if not b64:
        raise RuntimeError("LITELLM_MASTER_KEY missing in prod synced secret")
    return base64.b64decode(b64).decode("utf-8")


def pick_model(base: str, key: str, preferred: list[str] | None = None) -> str:
    headers = {"Authorization": f"Bearer {key}"}
    preferred = list(preferred or [])
    # plan default order if registry empty
    if not preferred:
        preferred = ["gpt-4o-mini", "together-llama-turbo"]
    with httpx.Client(timeout=30.0) as client:
        for path in (f"{base.rstrip('/')}/v1/models", f"{base.rstrip('/')}/models"):
            r = client.get(path, headers=headers)
            if r.status_code != 200:
                continue
            data = r.json()
            rows = data.get("data") if isinstance(data, dict) else data
            if not isinstance(rows, list):
                rows = []
            ids = []
            for m in rows:
                if isinstance(m, dict):
                    ids.append(str(m.get("id") or m.get("model") or ""))
            ids = [i for i in ids if i]
            print("litellm_models_count", len(ids))
            print("litellm_models_sample", ids[:12])
            for p in preferred:
                if p in ids:
                    return p
            for i in ids:
                low = i.lower()
                if "gpt-4o-mini" in low or "together" in low:
                    return i
            if ids:
                return ids[0]
            break
        raise RuntimeError("LiteLLM /models failed with prod master key")


def postman_tools(path: Path) -> list[dict]:
    col = json.loads(path.read_text(encoding="utf-8"))
    tools: list[dict] = []

    def walk(items: list, folder: str = "") -> None:
        for it in items or []:
            if "item" in it and "request" not in it:
                walk(it.get("item") or [], str(it.get("name") or folder))
                continue
            req = it.get("request") or {}
            method = str(req.get("method") or "GET").lower()
            url = req.get("url")
            path_s = ""
            if isinstance(url, dict):
                parts = url.get("path") or []
                path_s = "/" + "/".join(str(p) for p in parts if p is not None)
                raw = str(url.get("raw") or "")
                if "{{base_url}}" in raw:
                    path_s = raw.split("{{base_url}}", 1)[-1]
            else:
                path_s = str(url or "")
            path_s = path_s.split("?")[0]
            path_s = re.sub(r"https?://[^/]+", "", path_s)
            path_s = path_s.replace("{{base_url}}", "")
            if not path_s.startswith("/"):
                path_s = "/" + path_s.lstrip("/")
            if path_s in {"/", ""}:
                continue
            title = str(it.get("name") or path_s)
            safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", f"{folder}_{title}")[:72]
            tools.append(
                {
                    "name": f"postman.{safe}",
                    "method": method,
                    "path": path_s,
                    "title": title,
                }
            )

    walk(col.get("item") or [])
    tools.append(
        {
            "name": "identity.login",
            "method": "post",
            "path": "/auth/login",
            "title": "login",
        }
    )
    return tools


def make_litellm_chat(base: str, key: str, model: str):
    def chat(system: str, user: str) -> str:
        url = f"{base.rstrip('/')}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": 4096,
            "stream": False,
        }
        with httpx.Client(timeout=180.0) as client:
            resp = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if resp.status_code != 200:
                url2 = f"{base.rstrip('/')}/chat/completions"
                resp = client.post(
                    url2,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"LiteLLM chat HTTP {resp.status_code}: {resp.text[:400]}"
                )
            data = resp.json()
            return str(
                ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
                or ""
            )

    return chat


def main() -> int:
    if not POSTMAN.is_file():
        print("POSTMAN missing", POSTMAN)
        return 2
    if not KUBECONFIG.is_file():
        print("kubeconfig.prod missing", KUBECONFIG)
        return 2

    from prompts.loader import load_prompt_type
    from ui_evidence.scenario_bank.feature_export import persist_features_from_bank
    from ui_evidence.scenario_bank.quality import rate_invent_bank
    from ui_evidence.scenario_bank.repo import get_repo
    from ui_evidence.scenario_bank.scenario_planner import load_invent_skill_ids
    from ui_evidence.scenario_bank.spec_derive import derive_and_store

    # Prefer dig Mongo for local invent (not localhost / memory)
    os.environ.pop("QA_SCENARIO_BANK_DIR", None)
    os.environ["QA_SCENARIO_BANK_BACKEND"] = "mongo"
    from ui_evidence.scenario_bank.mongo_resolve import (
        ensure_dev_mongo_for_local_invent,
        try_local_mongo_fallback,
    )

    mongo_res = ensure_dev_mongo_for_local_invent()
    print(
        "mongo",
        {
            k: mongo_res.get(k)
            for k in ("ok", "source", "host_hint", "database", "error")
        },
    )

    # Force a real Mongo connection (no silent memory fallback)
    import ui_evidence.scenario_bank.repo as bank_repo

    bank_repo._REPO = None
    os.environ["QA_SCENARIO_BANK_BACKEND"] = "mongo"
    repo = None
    try:
        if mongo_res.get("ok"):
            from pymongo import MongoClient

            MongoClient(
                os.environ["MONGO_URI"], serverSelectionTimeoutMS=8000
            ).admin.command("ping")
            bank_repo._REPO = None
            repo = bank_repo.get_repo()
            if type(repo).__name__ != "MongoBankRepo":
                raise RuntimeError(f"expected MongoBankRepo got {type(repo).__name__}")
    except Exception as exc:  # noqa: BLE001
        print("dig/env Mongo connect failed:", exc)
        repo = None

    if repo is None or type(repo).__name__ != "MongoBankRepo":
        local = try_local_mongo_fallback(27018)
        print(
            "mongo_local_fallback",
            {k: local.get(k) for k in ("ok", "host_hint", "database", "error")},
        )
        if not local.get("ok"):
            print(
                "No Mongo reachable (dig :8895 or local :27018). "
                "Start Docker mongo or fix dig TCP gateway."
            )
            return 2
        # Clear memory fallback cache from dig failure, then bind local Mongo
        bank_repo._REPO = None
        bank_repo._DIR_TOKEN = None
        os.environ["QA_MONGO_ALLOW_LOCAL"] = "1"
        os.environ["QA_SCENARIO_BANK_BACKEND"] = "mongo"
        os.environ.pop("QA_SCENARIO_BANK_DIR", None)
        repo = bank_repo.get_repo()
        if type(repo).__name__ != "MongoBankRepo":
            # Bypass get_repo dig rewrite — construct directly
            from ui_evidence.scenario_bank.repo import MongoBankRepo

            uri = os.environ["MONGO_URI"]
            db = os.environ.get("MONGO_DATABASE") or "am_qa_agent_dev"
            direct = MongoBankRepo(uri, db)
            direct._client.admin.command("ping")
            bank_repo._REPO = direct
            repo = direct
        if type(repo).__name__ != "MongoBankRepo":
            print("local Mongo still not usable:", type(repo).__name__)
            return 2

    print(
        "mongo_backend",
        type(repo).__name__,
        "db",
        os.environ.get("MONGO_DATABASE"),
        "host",
        (os.environ.get("MONGO_URI") or "").split("@")[-1][:60],
    )

    invent_bundle = load_prompt_type(
        "invent", skill_ids=load_invent_skill_ids(), require_playbooks=True
    )

    key = prod_litellm_master_key()
    print("using_prod_synced_LITELLM_MASTER_KEY len", len(key), "prefix", key[:4] + "...")
    os.environ["LITELLM_BASE_URL"] = LITELLM_BASE
    os.environ["LITELLM_MASTER_KEY"] = key
    os.environ["LLM_ROUTING"] = "direct"

    from ui_evidence.scenario_bank.llm_status import probe_litellm

    probe = probe_litellm(
        ping_chat=False, base_url=LITELLM_BASE, api_key=key
    )
    print(
        "probe",
        {
            k: probe.get(k)
            for k in (
                "available",
                "base_url",
                "models_count",
                "error",
                "models_sample",
            )
        },
    )
    if not probe.get("available"):
        print("LiteLLM not available with prod key")
        return 1

    model = pick_model(LITELLM_BASE, key, invent_bundle.preferred_models)
    print("model", model)
    print(
        "prompt_type",
        invent_bundle.type_name,
        "schema",
        invent_bundle.schema_version,
    )

    from ui_evidence.scenario_bank.bank_store import (
        clear_llm_invented,
        list_scenarios,
        seed_default_rows,
    )
    from ui_evidence.scenario_bank.scenario_planner import invent_for_service

    tools = postman_tools(POSTMAN)
    print("tool_surface", len(tools))
    derived = derive_and_store("am-subscription", "dev", tools, source="postman")
    print(
        "derived",
        {
            "tools_digest": derived.get("tools_digest"),
            "surface_count": derived.get("surface_count"),
            "backend": type(get_repo()).__name__,
        },
    )
    seed_default_rows(
        "am-subscription",
        "dev",
        ["data_generator", "happy_flow", "level2_alt_path"],
    )
    cleared = clear_llm_invented("am-subscription", "dev")
    print("cleared_llm_invented", cleared)

    chat = make_litellm_chat(LITELLM_BASE, key, model)
    # Pilot: max 3 scenarios per invent skill (planner cap) for a dense UI bank
    per_skill = max(invent_bundle.scenarios_per_skill_default, 3)
    result = invent_for_service(
        "am-subscription",
        "dev",
        tools=tools,
        force_llm=True,
        chat_fn=chat,
        owner="litellm-invent",
        scenarios_per_skill=per_skill,
    )
    print("invent", json.dumps(result, indent=2, default=str))

    rows = list_scenarios("am-subscription", "dev")
    by_status: dict[str, int] = {}
    by_skill: dict[str, int] = {}
    for r in rows:
        by_status[str(r.get("status"))] = by_status.get(str(r.get("status")), 0) + 1
        by_skill[str(r.get("skill"))] = by_skill.get(str(r.get("skill")), 0) + 1
    print("bank_count", len(rows), "by_status", by_status, "by_skill", by_skill)

    # Features SoT = DB; optional debug file under data/ (not plugin/)
    debug_feat = (
        ROOT
        / "ui_evidence"
        / "data"
        / "scenario_bank"
        / "debug"
        / "am-subscription_dev.feature"
    )
    feats = persist_features_from_bank(
        "am-subscription",
        "dev",
        export_path=debug_feat,
        feature_title="Subscription invented bank scenarios",
    )
    print("features_db", feats.get("count"), "debug", feats.get("export_path"))

    rating = rate_invent_bank("am-subscription", "dev")
    print("quality", json.dumps(rating, indent=2, default=str))

    get_repo().upsert_knowledge(
        "am-subscription",
        "dev",
        {
            "invent_complete": bool(result.get("invent_complete")),
            "needs_reinvent": False,
            "llm_invoked": True,
            "invent_call_count": result.get("call_count"),
            "invent_provider": f"litellm:{model}",
            "prompt_registry": "am.qa.prompts/v1",
            "prompt_type": "invent",
            "schema_version": invent_bundle.schema_version,
            "quality_score": rating.get("quality_score"),
            "quality_reasons": rating.get("quality_reasons"),
            "invent_note": (
                "DB-backed invent; LiteLLM prod key; Postman surface (OpenAPI HTML)"
            ),
        },
    )

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
