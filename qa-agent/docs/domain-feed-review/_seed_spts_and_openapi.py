"""Create catalog-external SPTs + seed OpenAPI from am-specs for dig/preprod/prod."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import urllib.request
import yaml

SPECS = Path(r"f:\am-repos\am-repos\am-specs")
QA = Path(r"f:\am-repos\am-repos\am-qa-agents\qa-agent")
REVIEW = Path(__file__).resolve().parent
EXT = QA / "catalog-external"
API = "http://127.0.0.1:8150"
ENVS = ["dev", "preprod", "prod"]


def http_json(method: str, url: str, body: dict | None = None) -> tuple[int, dict | str]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            raw = res.read().decode("utf-8")
            try:
                return res.status, json.loads(raw)
            except Exception:
                return res.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def write_spt(entry: dict) -> Path:
    sid = entry["id"]
    envs = entry.get("environments") or {}
    spt_meta = entry.get("spt") or {}
    dest_dir = EXT / sid
    dest_dir.mkdir(parents=True, exist_ok=True)
    # Prefer host roots that match am-subscription style when path has prefix
    targets = {}
    for env, url in envs.items():
        if not url:
            continue
        # Keep full service base from am-specs targets — openapi seed supplies doc.
        targets[env] = url
    openapi_path = "/openapi.json"
    oa = entry.get("openapi") or {}
    # mirror common spring / fastapi paths from catalog when known
    catalog_row = None
    spt = {
        "apiVersion": "am.spt/v1",
        "kind": "ServiceLoadTest",
        "service": sid,
        "label": sid,
        "enabled": True,
        "runtime": "unknown",
        "description": f"Domain feed registration from am-specs ({sid})",
        "source": {
            "repo": (spt_meta or {}).get("repo"),
            "path": (spt_meta or {}).get("path"),
        },
        "targets": targets,
        "openapi": {"path": openapi_path},
    }
    path = dest_dir / "spt.yaml"
    path.write_text(yaml.safe_dump(spt, sort_keys=False), encoding="utf-8")
    return path


def load_openapi_doc(sid: str) -> dict | None:
    j = SPECS / "services" / sid / "openapi.json"
    y = SPECS / "services" / sid / "openapi.yaml"
    if j.exists():
        return json.loads(j.read_text(encoding="utf-8"))
    if y.exists():
        return yaml.safe_load(y.read_text(encoding="utf-8"))
    return None


def main() -> int:
    cat = yaml.safe_load((REVIEW / "catalog.yaml").read_text(encoding="utf-8"))
    results = []
    for entry in cat["services"]:
        sid = entry["id"]
        spt_path = write_spt(entry)
        print("spt", spt_path)
        doc = load_openapi_doc(sid)
        if not doc:
            results.append({"id": sid, "error": "no openapi snapshot"})
            continue
        envs = entry.get("environments") or {}
        for env in ENVS:
            body = {
                "document": doc,
                "target_url": envs.get(env) or "",
                "openapi_url": f"am-specs://services/{sid}/openapi",
            }
            code, out = http_json(
                "POST",
                f"{API}/api/catalog/{sid}/openapi/seed?environment={env}&from_payload_set=false",
                body,
            )
            ok = isinstance(out, dict) and (out.get("ok") is True or code == 200)
            print("seed", sid, env, code, (out if not isinstance(out, dict) else {k: out.get(k) for k in ('ok','error','operation_count','environment')}))
            results.append({"id": sid, "env": env, "http": code, "out": out if isinstance(out, dict) else str(out)[:200]})
            # overview probe
            ocode, oout = http_json(
                "GET",
                f"{API}/api/services/{sid}/overview?environment={env}&runs_limit=3",
            )
            print("overview", sid, env, ocode)
            results.append({"id": sid, "env": env, "overview_http": ocode})

    report = REVIEW / "SEED_REPORT.json"
    report.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print("wrote", report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
