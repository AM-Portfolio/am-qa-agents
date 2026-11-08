"""Collapse multi-variant examples into one primary SPT row + variants meta."""
from __future__ import annotations

from typing import Any

from specs.data_gen.constants import CASE_KIND_PRIORITY


def case_kind_of(row: dict[str, Any]) -> str:
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    ck = str(meta.get("case_kind") or row.get("case_kind") or "").strip().lower()
    return ck or "happy"


def expect_status_of(row: dict[str, Any]) -> int | None:
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    if meta.get("expect_status") is not None:
        try:
            return int(meta["expect_status"])
        except (TypeError, ValueError):
            pass
    resp = row.get("response") if isinstance(row.get("response"), dict) else {}
    if resp.get("status") is not None:
        try:
            return int(resp["status"])
        except (TypeError, ValueError):
            pass
    ck = case_kind_of(row)
    # Technical kinds often encode status in variant_id / name
    for token, code in (
        ("unauthorized", 401),
        ("forbidden", 403),
        ("not_found", 404),
        ("bad_request", 400),
        ("conflict", 409),
        ("too_many_requests", 429),
        ("internal_error", 500),
        ("bad_gateway", 502),
        ("service_unavailable", 503),
        ("gateway_timeout", 504),
    ):
        blob = f"{row.get('name') or ''} {meta.get('variant_id') or ''} {ck}"
        if token in blob.lower():
            return code
    if ck in {"happy", "must_work", "cross_flow", "crud"}:
        return 200
    return None


def _score(row: dict[str, Any]) -> int:
    return CASE_KIND_PRIORITY.get(case_kind_of(row), 10)


def collapse_by_api_id(examples: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Pick preferred primary per api_id; stash siblings under meta.variants."""
    buckets: dict[str, list[dict[str, Any]]] = {}
    for raw in examples:
        if not isinstance(raw, dict):
            continue
        api_id = str(raw.get("api_id") or "").strip()
        if not api_id:
            req = raw.get("request") if isinstance(raw.get("request"), dict) else {}
            method = str(req.get("method") or raw.get("method") or "GET").lower()
            path = str(req.get("path") or raw.get("path") or "")
            api_id = f"{method}_{path}".replace("/", "_") or "unknown"
        buckets.setdefault(api_id, []).append(raw)

    out: dict[str, dict[str, Any]] = {}
    for api_id, rows in buckets.items():
        ranked = sorted(rows, key=_score, reverse=True)
        primary = dict(ranked[0])
        meta = dict(primary.get("meta") or {}) if isinstance(primary.get("meta"), dict) else {}
        meta["case_kind"] = case_kind_of(primary)
        exp = expect_status_of(primary)
        if exp is not None:
            meta["expect_status"] = exp
        variants: list[dict[str, Any]] = []
        for sib in ranked[1:]:
            sm = sib.get("meta") if isinstance(sib.get("meta"), dict) else {}
            variants.append(
                {
                    "api_id": api_id,
                    "name": sib.get("name"),
                    "case_kind": case_kind_of(sib),
                    "expect_status": expect_status_of(sib),
                    "variant_id": (sm or {}).get("variant_id"),
                    "request": sib.get("request"),
                    "response": sib.get("response"),
                    "meta": sm,
                }
            )
        if variants:
            meta["variants"] = variants
        primary["meta"] = meta
        primary["api_id"] = api_id
        out[api_id] = primary
    return out
