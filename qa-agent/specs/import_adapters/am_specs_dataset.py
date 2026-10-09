"""am-specs dataset / export_qa payload_set → AmImportBundle."""
from __future__ import annotations

from typing import Any

from specs.import_adapters.base import AmImportBundle, AmImportItem


def _as_dict(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    return None


class AmSpecsDatasetAdapter:
    """Accepts export_qa POST body or payload_set document."""

    format_id = "am-specs-dataset"

    def detect(self, raw: Any) -> bool:
        data = _as_dict(raw)
        if not data:
            return False
        if str(data.get("format") or "").lower() == "am-specs-dataset":
            return True
        src = data.get("source")
        if isinstance(src, dict) and str(src.get("kind") or "") == "am-specs-datasets":
            return True
        if isinstance(data.get("payload_set"), dict) and (
            data.get("apis") is not None or "service" in data.get("payload_set", {})
        ):
            return True
        # Bare payload_set doc
        if isinstance(data.get("apis"), dict) and data.get("service") and (
            data.get("source") or data.get("label")
        ):
            kind = ""
            if isinstance(data.get("source"), dict):
                kind = str(data["source"].get("kind") or "")
            return kind == "am-specs-datasets" or str(data.get("label") or "").startswith(
                "data-gen-"
            )
        return False

    def parse_environment(self, raw: Any) -> dict[str, str]:
        data = _as_dict(raw) or {}
        out: dict[str, str] = {}
        # var_defaults style {key: value} or {values: [{key,value}]}
        if isinstance(data.get("values"), list):
            for row in data["values"]:
                if isinstance(row, dict) and row.get("key"):
                    out[str(row["key"])] = "" if row.get("value") is None else str(row["value"])
            return out
        for k, v in data.items():
            if k in {"values", "name", "_postman_variable_scope"}:
                continue
            if isinstance(v, (str, int, float, bool)):
                out[str(k)] = str(v)
        return out

    def parse_collection(self, raw: Any, *, service: str) -> AmImportBundle:
        data = _as_dict(raw) or {}
        doc = data
        if isinstance(data.get("payload_set"), dict):
            doc = data["payload_set"]
        svc = str(doc.get("service") or data.get("service") or service or "").strip()
        if not svc:
            raise ValueError("am-specs-dataset import requires service")
        src = doc.get("source") if isinstance(doc.get("source"), dict) else {}
        profile = str(src.get("profile") or data.get("profile") or "prod")
        label = str(
            data.get("label") or doc.get("label") or f"data-gen-{profile}"
        ).strip()
        warnings: list[str] = []
        items: list[AmImportItem] = []
        env: dict[str, str] = {}
        env_block = data.get("env") or doc.get("env") or data.get("var_defaults")
        if isinstance(env_block, dict):
            env = self.parse_environment(env_block)

        apis = doc.get("apis")
        examples: list[dict[str, Any]] = []
        if isinstance(apis, dict):
            examples = [v for v in apis.values() if isinstance(v, dict)]
        elif isinstance(apis, list):
            examples = [v for v in apis if isinstance(v, dict)]
        elif isinstance(doc.get("examples"), list):
            examples = [v for v in doc["examples"] if isinstance(v, dict)]

        from specs.data_gen.prefer import collapse_by_api_id, expect_status_of

        collapsed = collapse_by_api_id(examples)
        for api_id, entry in collapsed.items():
            req = entry.get("request") if isinstance(entry.get("request"), dict) else {}
            method = str(req.get("method") or entry.get("method") or "GET").upper()
            path = str(req.get("path") or entry.get("path") or "")
            if not path:
                warnings.append(f"skip {api_id}: missing path")
                continue
            meta = dict(entry.get("meta") or {}) if isinstance(entry.get("meta"), dict) else {}
            meta.setdefault("source", "import:am-specs-dataset")
            meta["profile"] = profile
            exp = expect_status_of(entry)
            if exp is not None:
                meta["expect_status"] = exp
            # Stash response + meta on item via headers marker is awkward;
            # AmImportItem extended with optional extra via auth_hint unused —
            # put JSON in a side channel: we use a private attr after construct.
            item = AmImportItem(
                api_id=str(api_id),
                name=str(entry.get("name") or meta.get("variant_id") or "data-gen"),
                method=method,
                path=path,
                path_params=dict(req.get("path_params") or {}),
                query=dict(req.get("query") or {}),
                headers=dict(req.get("headers") or {}),
                body=req.get("body"),
                auth_hint=str(meta.get("case_kind") or ""),
            )
            # Attach rich fields for importer (not part of dataclass protocol consumers)
            setattr(item, "extra_meta", meta)
            setattr(item, "extra_response", dict(entry.get("response") or {}))
            items.append(item)

        return AmImportBundle(
            source=self.format_id,
            service=svc,
            label=label,
            env=env,
            items=items,
            warnings=warnings,
        )
