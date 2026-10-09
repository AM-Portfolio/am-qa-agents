
import json
from pathlib import Path

tools = json.loads(Path("/invent/invent_tools.json").read_text(encoding="utf-8"))
print("tools", len(tools), flush=True)

from ui_evidence.scenario_bank.spec_derive import derive_and_store
from ui_evidence.scenario_bank.bank_store import seed_default_rows, load_bank
from ui_evidence.scenario_bank.scenario_planner import invent_for_service
from ui_evidence.scenario_bank.feature_export import persist_features_from_bank
from ui_evidence.scenario_bank.quality import rate_invent_bank
from ui_evidence.scenario_bank.repo import get_repo

service, env = "am-market-data", "dev"
derive_and_store(service, env, tools, source="payload-set")
seed_default_rows(
    service,
    env,
    [
        "data_generator",
        "happy_flow",
        "level2_alt_path",
        "negative",
        "boundary",
        "security",
    ],
)
out = invent_for_service(
    service,
    env,
    tools=tools,
    force_llm=True,
    owner="seed-job",
    scenarios_per_skill=2,
)
print("invent", json.dumps(out, default=str)[:2000], flush=True)
feats = persist_features_from_bank(service, env)
print("features", feats.get("count"), flush=True)
rating = rate_invent_bank(service, env)
print("quality", json.dumps(rating, default=str)[:500], flush=True)
bank = load_bank(service, env)
print(
    "bank_count",
    len(bank.get("scenarios") or []),
    "invent_complete",
    bank.get("invent_complete"),
    flush=True,
)
get_repo().upsert_knowledge(
    service,
    env,
    {
        "invent_complete": bool(out.get("invent_complete")),
        "needs_reinvent": False,
        "llm_invoked": bool(out.get("llm_invoked")),
        "invent_call_count": out.get("call_count"),
        "invent_note": "seed-job from payload-set tools",
    },
)
print("DONE", flush=True)
