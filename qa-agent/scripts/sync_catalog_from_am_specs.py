#!/usr/bin/env python3
"""Build catalog-external/<service>/spt.yaml from am-specs tools.json (full API list).

Writes explicit apis[] so Spec UI shows every pack tool (not live springdoc).
Skips agent services that are not product HTTP APIs for SPT load.

Usage:
  python qa-agent/scripts/sync_catalog_from_am_specs.py
  python qa-agent/scripts/sync_catalog_from_am_specs.py --apply-dev  # kubectl apply bundle
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

QA_ROOT = Path(__file__).resolve().parents[1]
OUT = QA_ROOT / "catalog-external"
SPECS = Path(r"f:/am-repos/am-repos/am-specs/services")

# Match publish-spt-catalogs AGENT_SERVICES — keep product apps only for Spec UI.
SKIP = frozenset(
    {
        "am-mcp-server",
        "am-support-agent",
        "am-db-agent",
        "am-fin-agent",
        "am-qa-agents",
        "am-qa-agents-specs",
        "am-ui-test-agent",
        "am-tool-agent",
        "am-asrax-corp",  # optional: include if wanted
    }
)


def _apis_from_tools(tools_doc: dict) -> list[dict]:
    apis: list[dict] = []
    seen: set[str] = set()
    for t in tools_doc.get("tools") or []:
        meta = t.get("_meta") or {}
        fn = (t.get("function") or {}) if isinstance(t.get("function"), dict) else {}
        name = str(meta.get("tool_name") or fn.get("name") or meta.get("op_id") or "")
        if not name or name in seen:
            continue
        seen.add(name)
        method = str(meta.get("method") or "get").upper()
        path = str(meta.get("path") or "/")
        # Substitute path params with examples from function.parameters
        props = ((fn.get("parameters") or {}).get("properties") or {}) if fn else {}
        for pname, pschema in props.items():
            if not isinstance(pschema, dict):
                continue
            if pschema.get("x-param-in") == "path" or pname in (meta.get("path_params") or []):
                ex = pschema.get("example")
                if ex is None and "examples" in pschema:
                    ex = next(iter(pschema["examples"]), None)
                if ex is not None:
                    path = path.replace("{" + pname + "}", str(ex))
        query: dict = {}
        for pname, pschema in props.items():
            if not isinstance(pschema, dict):
                continue
            if pschema.get("x-param-in") == "query":
                ex = pschema.get("example")
                if ex is not None:
                    query[pname] = ex
        apis.append(
            {
                "id": name.replace("api_", "", 1) if name.startswith("api_") else name,
                "name": name,
                "method": method,
                "path": path,
                "headers": {},
                "query": query,
                "body": None,
                "checks": ["status_2xx"],
                "group": meta.get("group") or "core",
            }
        )
    return apis


def _targets_from_tools(tools_doc: dict, service: str) -> dict[str, str]:
    for t in tools_doc.get("tools") or []:
        meta = t.get("_meta") or {}
        bu = meta.get("base_urls")
        if isinstance(bu, dict) and bu:
            return {str(k): str(v) for k, v in bu.items()}
        if meta.get("base_url"):
            return {"dev": str(meta["base_url"])}
    # fallbacks
    slug = service.replace("am-", "", 1) if service.startswith("am-") else service
    return {
        "dev": f"https://am-dev.asrax.in/{slug}",
        "preprod": f"https://am-preprod.asrax.in/{slug}",
        "prod": f"https://am.asrax.in/{slug}",
    }


def build_one(service_dir: Path) -> tuple[str, dict] | None:
    tools_path = service_dir / "tools.json"
    if not tools_path.is_file():
        return None
    sid = service_dir.name
    if sid in SKIP:
        return None
    doc = json.loads(tools_path.read_text(encoding="utf-8"))
    apis = _apis_from_tools(doc)
    if not apis:
        return None
    reg = {
        "apiVersion": "am.spt/v1",
        "kind": "ServiceLoadTest",
        "service": sid,
        "label": sid,
        "enabled": True,
        "owners": ["speckit"],
        "description": (
            f"Generated from am-specs/services/{sid}/tools.json "
            f"({len(apis)} tools) — Spec UI source of truth."
        ),
        "source": {
            "repo": "am-specs",
            "path": f"services/{sid}/tools.json",
            "team": "speckit",
        },
        "targets": _targets_from_tools(doc, sid),
        "apis": apis,
    }
    return sid, reg


def write_bundle(regs: dict[str, dict]) -> Path:
    data = {f"{sid}.yaml": yaml.safe_dump(reg, sort_keys=False) for sid, reg in sorted(regs.items())}
    cm = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": "spt-catalog-bundle",
            "namespace": "am-agents-dev",
            "labels": {"app.kubernetes.io/part-of": "am-qa-agents"},
        },
        "data": data,
    }
    out = QA_ROOT / "dist" / "spt-catalog-bundle.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    # size check
    text = yaml.safe_dump(cm, sort_keys=False)
    out.write_text(text, encoding="utf-8")
    print(f"bundle bytes={len(text.encode('utf-8'))} limit=1048576")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--specs", type=Path, default=SPECS)
    ap.add_argument("--apply-dev", action="store_true")
    args = ap.parse_args()
    if not args.specs.is_dir():
        print("am-specs/services missing", file=sys.stderr)
        return 1

    regs: dict[str, dict] = {}
    for d in sorted(args.specs.iterdir()):
        if not d.is_dir():
            continue
        built = build_one(d)
        if not built:
            continue
        sid, reg = built
        dest = OUT / sid
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "spt.yaml").write_text(yaml.safe_dump(reg, sort_keys=False), encoding="utf-8")
        regs[sid] = reg
        print(f"{sid}: apis={len(reg['apis'])}")

    print(f"wrote {len(regs)} registrations under {OUT}")
    bundle = write_bundle(regs)
    print("wrote", bundle)

    if args.apply_dev:
        env = os.environ.copy()
        env.setdefault("KUBECONFIG", str(Path.home() / ".asrax" / "kubeconfig.dev"))
        r = subprocess.run(
            ["kubectl", "apply", "-f", str(bundle)],
            env=env,
            check=False,
        )
        return r.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
