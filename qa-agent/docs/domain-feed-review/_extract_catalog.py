"""One-shot helper: extract review catalog from am-specs. Run then delete optional."""
from __future__ import annotations

import json
from pathlib import Path

try:
    import yaml
except ImportError:
    raise SystemExit("pyyaml required")

ROOT = Path(r"f:\am-repos\am-repos\am-specs")
IDS = [
    "am-market-data",
    "am-news",
    "am-parser",
    "am-portfolio",
    "am-analysis",
    "am-trade-management-service",
    "am-oms",
    "am-subscription",
]
DOMAIN_HINT = {
    "am-market-data": "market",
    "am-news": "market",
    "am-parser": "market",
    "am-portfolio": "portfolio",
    "am-analysis": "portfolio",
    "am-trade-management-service": "trade",
    "am-oms": "trade",
    "am-subscription": "platform",
}


def load_catalog() -> dict:
    raw = yaml.safe_load((ROOT / "catalog" / "services.yaml").read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "services" in raw:
        services = raw["services"]
    else:
        services = raw
    by_id: dict = {}
    if isinstance(services, list):
        for s in services:
            if isinstance(s, dict) and s.get("id"):
                by_id[s["id"]] = s
    elif isinstance(services, dict):
        for k, v in services.items():
            if isinstance(v, dict):
                by_id[v.get("id", k)] = v
    return by_id


def envs_of(s: dict) -> dict:
    for key in ("targets", "environments", "urls", "bases", "base_urls"):
        e = s.get(key)
        if isinstance(e, dict) and any(k in e for k in ("dev", "preprod", "prod")):
            return {k: e.get(k) for k in ("dev", "preprod", "prod")}
    out = {}
    for k in ("dev", "preprod", "prod"):
        if s.get(k):
            out[k] = s[k]
    return out


def count_ops(service_id: str) -> int | None:
    path = ROOT / "services" / service_id / "openapi.yaml"
    if not path.exists():
        path = ROOT / "services" / service_id / "openapi.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    paths = (data or {}).get("paths") or {}
    n = 0
    for _p, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for m in methods:
            if m.lower() in ("get", "post", "put", "patch", "delete", "head", "options"):
                n += 1
    return n


def main() -> None:
    by_id = load_catalog()
    out = {
        "title": "Domain feed review catalog",
        "source": "am-specs/catalog/services.yaml",
        "environments": ["dev", "preprod", "prod"],
        "services": [],
    }
    for i, sid in enumerate(IDS, start=1):
        s = by_id.get(sid) or {}
        oa_yaml = ROOT / "services" / sid / "openapi.yaml"
        oa_json = ROOT / "services" / sid / "openapi.json"
        dg = ROOT / "templates" / "data-gen" / "service" / sid
        entry = {
            "id": sid,
            "priority": i,
            "domain": s.get("domain") or DOMAIN_HINT.get(sid),
            "enabled": s.get("enabled", s.get("status") == "active"),
            "status": s.get("status"),
            "environments": envs_of(s),
            "openapi": {
                "yaml": str(oa_yaml.relative_to(ROOT)).replace("\\", "/")
                if oa_yaml.exists()
                else None,
                "json": str(oa_json.relative_to(ROOT)).replace("\\", "/")
                if oa_json.exists()
                else None,
                "operations": count_ops(sid),
            },
            "data_gen": {
                "template_dir": str(dg.relative_to(ROOT)).replace("\\", "/")
                if dg.exists()
                else None,
                "business_yaml": (dg / "business.yaml").exists() if dg.exists() else False,
            },
            "spt": s.get("spt") or s.get("source") or s.get("repo"),
        }
        out["services"].append(entry)
        print(sid, entry["environments"], entry["openapi"]["operations"])

    dest = Path(__file__).resolve().parent / "catalog.yaml"
    dest.write_text(yaml.safe_dump(out, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print("wrote", dest)


if __name__ == "__main__":
    main()
