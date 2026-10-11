"""CI / GitHub provenance fields carried on SPT runs (Overview chips)."""

from __future__ import annotations

from typing import Any

# Persisted on run top-level and payloads_used.run_params.
CI_PROVENANCE_KEYS: tuple[str, ...] = (
    "git_sha",
    "git_ref",
    "committer_email",
    "committer_name",
    "trigger_source",
    "github_repository",
    "github_run_id",
    "github_run_url",
    "github_workflow",
    "github_event_name",
    "commit_message",
    "temporal_workflow_id",
    "tracking_id",
    "dataset_profile",
)



def extract_ci_provenance(src: Any) -> dict[str, Any]:
    """Pull non-empty provenance keys from a dict, pydantic model, or object."""
    if src is None:
        return {}
    out: dict[str, Any] = {}
    for key in CI_PROVENANCE_KEYS:
        if isinstance(src, dict):
            val = src.get(key)
        else:
            val = getattr(src, key, None)
        if val is None:
            continue
        if isinstance(val, str) and not val.strip():
            continue
        out[key] = val
    return out


def merge_ci_provenance(record: dict[str, Any], provenance: dict[str, Any]) -> dict[str, Any]:
    """Copy provenance onto run top-level and into payloads_used.run_params (in place)."""
    if not provenance:
        return record
    for key, val in provenance.items():
        if record.get(key) in (None, ""):
            record[key] = val
    payloads = record.setdefault("payloads_used", {})
    if not isinstance(payloads, dict):
        payloads = {}
        record["payloads_used"] = payloads
    run_params = payloads.setdefault("run_params", {})
    if not isinstance(run_params, dict):
        run_params = {}
        payloads["run_params"] = run_params
    for key, val in provenance.items():
        if run_params.get(key) in (None, ""):
            run_params[key] = val
    return record
