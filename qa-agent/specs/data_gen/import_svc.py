"""Import am-specs data-gen packs into Specs payload sets (+ optional workflows)."""
from __future__ import annotations

from typing import Any

from specs.data_gen.constants import PAYLOAD_SET_LABEL_PREFIX
from specs.data_gen.pack import disk_profile_for_suite, resolve_import_document
from specs.data_gen.workflows import sync_cross_flow_workflows
from specs.import_adapters import import_collection_to_payload_set


def import_data_gen(
    *,
    service: str,
    profile: str = "default",
    environment: str = "dev",
    body: dict[str, Any] | None = None,
    pack_path: str | None = None,
    make_active: bool = True,
    sync_workflows: bool = True,
    bump_set: bool = True,
) -> dict[str, Any]:
    disk = disk_profile_for_suite(profile)
    try:
        resolved = resolve_import_document(
            service=service,
            profile=disk,
            body=body,
            pack_path=pack_path,
            environment=environment,
        )
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "error": "pack_not_found",
            "message": str(exc),
            "service": service,
            "profile": disk,
        }

    label = str(resolved.get("label") or f"{PAYLOAD_SET_LABEL_PREFIX}{disk}")
    collection = {
        "format": "am-specs-dataset",
        "service": service,
        "label": label,
        "payload_set": resolved.get("payload_set"),
        "env": resolved.get("env"),
        "profile": disk,
    }
    env = resolved.get("env")
    out = import_collection_to_payload_set(
        service=service,
        collection=collection,
        environment=env if isinstance(env, dict) else None,
        format="am-specs-dataset",
        label=label,
        make_active=make_active,
        bump_set=bump_set,
    )
    if not out.get("ok"):
        return {
            **out,
            "ok": False,
            "error": "empty_import",
            "message": "Refusing to activate empty data-gen import",
            "profile": disk,
        }

    workflow_sync: dict[str, Any] = {"upserted": [], "pruned": [], "skipped": True}
    examples: list[dict[str, Any]] = []
    pack_dir = resolved.get("pack_dir")
    if pack_dir and sync_workflows:
        from pathlib import Path

        from specs.data_gen.pack import load_examples_from_pack_dir

        # Prefer on-disk case_kind folders (avoids duplicate collapsed+raw rows)
        examples = load_examples_from_pack_dir(Path(pack_dir))
    else:
        ps = resolved.get("payload_set") or {}
        apis = ps.get("apis") if isinstance(ps, dict) else {}
        if isinstance(apis, dict):
            for entry in apis.values():
                if not isinstance(entry, dict):
                    continue
                examples.append(entry)
                meta = entry.get("meta") if isinstance(entry.get("meta"), dict) else {}
                for var in meta.get("variants") or []:
                    if isinstance(var, dict):
                        examples.append(var)

    if sync_workflows:
        workflow_sync = sync_cross_flow_workflows(
            service=service,
            profile=disk,
            examples=examples,
            payload_set_version=int(out.get("payload_set_version") or 0),
            prune=True,
        )
        workflow_sync["skipped"] = False

    return {
        **out,
        "ok": True,
        "profile": disk,
        "suite": profile if profile in {"default", "full", "premium"} else "default",
        "pack_dir": resolved.get("pack_dir"),
        "workflow_sync": workflow_sync,
        "handoff": {
            "service": service,
            "profile": disk,
            "environment": environment,
            "payload_set_version": out.get("payload_set_version"),
            "workflow_sync": {
                "upserted": workflow_sync.get("upserted") or [],
                "flow_ids": workflow_sync.get("flow_ids") or [],
            },
        },
    }


def import_services(
    services: list[str],
    *,
    profile: str = "default",
    environment: str = "dev",
    **kwargs: Any,
) -> dict[str, Any]:
    results = [
        import_data_gen(service=s, profile=profile, environment=environment, **kwargs)
        for s in services
        if str(s).strip()
    ]
    return {
        "ok": all(r.get("ok") for r in results) if results else False,
        "results": results,
        "count": len(results),
    }
