"""Build dig am-market-data SPT registration with explicit apis (springdoc broken)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

TEMP = Path(os.environ["TEMP"])
CFG = TEMP / "md-cfg.json"
RUN = TEMP / "md-run.json"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "catalog-external" / "am-market-data"
CM_PATH = Path(r"f:\am-repos\am-repos\am-gitops\manifests\dev\spt-catalog-bundle.yaml")


def main() -> None:
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    run = json.loads(RUN.read_text(encoding="utf-8"))
    selected = list(cfg.get("selected_api_ids") or [])
    overrides = {
        str(o.get("id")): o
        for o in (run.get("payloads_used") or {}).get("api_overrides") or []
        if o.get("id")
    }
    # Prefer selected order; append any extra override ids used in last green-ish run
    ordered = list(selected)
    for aid in overrides:
        if aid not in ordered:
            ordered.append(aid)
    apis: list[dict] = []
    missing: list[str] = []
    for aid in ordered:
        o = overrides.get(aid) or {}
        if not o.get("path"):
            missing.append(aid)
            continue
        path = str(o.get("path") or "/")
        for k, v in (o.get("path_params") or {}).items():
            path = path.replace("{" + str(k) + "}", str(v))
        apis.append(
            {
                "id": aid,
                "name": aid,
                "method": str(o.get("method") or "GET").upper(),
                "path": path,
                "headers": o.get("headers") or {},
                "query": o.get("query") or {},
                "body": o.get("body"),
                "checks": ["status_2xx"],
            }
        )
    reg = {
        "apiVersion": "am.spt/v1",
        "kind": "ServiceLoadTest",
        "service": "am-market-data",
        "label": "am-market-data",
        "enabled": True,
        # No runtime/openapi → load_service_apis uses explicit apis (dig springdoc SOE).
        "owners": ["market-team"],
        "description": (
            "Market Data SPT registration with explicit apis "
            "(live /v3/api-docs StackOverflowError on dig image)."
        ),
        "targets": {
            "dev": "https://am-dev.asrax.in/market",
            "preprod": "https://am-preprod.asrax.in/market",
            "prod": "https://am.asrax.in/market",
        },
        "apis": apis,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "spt.yaml").write_text(yaml.safe_dump(reg, sort_keys=False), encoding="utf-8")
    body = yaml.safe_dump(reg, sort_keys=False)
    cm = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": "spt-catalog-bundle",
            "namespace": "am-agents-dev",
            "labels": {"app.kubernetes.io/part-of": "am-qa-agents"},
        },
        "data": {"am-market-data.yaml": body},
    }
    CM_PATH.write_text(yaml.safe_dump(cm, sort_keys=False), encoding="utf-8")
    print("apis", len(apis), "missing", missing)
    print("wrote", OUT_DIR / "spt.yaml")
    print("wrote", CM_PATH)


if __name__ == "__main__":
    main()
