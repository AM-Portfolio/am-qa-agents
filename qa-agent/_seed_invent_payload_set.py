"""Seed active payload set from invent bank GET steps (subscription pilot)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from composition.env_bootstrap import load_env

load_env()

os.environ["QA_MONGO_ALLOW_LOCAL"] = "1"
os.environ["QA_SCENARIO_BANK_BACKEND"] = "mongo"
os.environ.setdefault(
    "MONGO_URI", "mongodb://127.0.0.1:27018/?directConnection=true"
)
os.environ.setdefault("MONGODB_URI", os.environ["MONGO_URI"])
os.environ.setdefault("MONGO_DATABASE", "am_qa_agent_dev")

from specs.payloads import payload_store as ps_mod
from specs.payloads.payload_store import (
    create_payload_set,
    get_payload_set,
    set_active_payload_set,
)
from ui_evidence.scenario_bank import repo as bank_repo
from ui_evidence.scenario_bank.bank_store import list_scenarios

bank_repo._REPO = None
bank_repo._DIR_TOKEN = None

rows = list_scenarios("am-subscription", "dev")
apis: dict = {}
for r in rows:
    skill = str(r.get("skill") or "")
    if skill in {"level5_abuse", "security"}:
        continue
    for st in r.get("steps") or []:
        if not isinstance(st, dict):
            continue
        method = str(st.get("method") or "get").upper()
        path = str(st.get("path") or "").strip()
        if not path or method not in {"GET", "HEAD"}:
            continue
        api_id = (
            f"invent.{skill}.{method.lower()}.{path.strip('/').replace('/', '_')}"
        )[:80]
        if api_id in apis:
            continue
        body = st.get("body") if isinstance(st.get("body"), (dict, list)) else None
        apis[api_id] = {
            "api_id": api_id,
            "method": method,
            "path": path,
            "headers": {"Accept": "application/json"},
            "query": st.get("query") if isinstance(st.get("query"), dict) else {},
            "body": body,
            "meta": {
                "source": "llm_invent",
                "skill": skill,
                "scenario_title": r.get("title"),
                "note": (
                    "Seeded from invent bank; live CF /subscription currently "
                    "returns SPA HTML — re-run ensure-working when API routes JSON."
                ),
            },
        }

ps = create_payload_set("am-subscription", label="invent-llm-dev", make_active=True)
ver = int(ps["version"])
full = get_payload_set("am-subscription", ver) or ps
full["apis"] = apis
full["label"] = "invent-llm-dev"
full["updated_at"] = ps_mod._now()
ps_mod._set_file_path("am-subscription", ver).write_text(
    json.dumps(full, indent=2, default=str), encoding="utf-8"
)
set_active_payload_set("am-subscription", ver)
print(json.dumps({"ok": True, "version": ver, "api_count": len(apis)}, indent=2))
