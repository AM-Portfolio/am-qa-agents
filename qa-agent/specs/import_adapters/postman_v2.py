"""Postman Collection v2.0 / v2.1 + Environment adapter."""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qs, urlparse

from specs.import_adapters.base import AmImportBundle, AmImportItem, slug_api_id


class PostmanV2Adapter:
    format_id = "postman"

    def detect(self, raw: Any) -> bool:
        data = _as_dict(raw)
        if not data:
            return False
        info = data.get("info")
        if isinstance(info, dict) and ("schema" in info or "name" in info) and "item" in data:
            schema = str(info.get("schema") or "")
            return "postman" in schema.lower() or bool(data.get("item"))
        # Environment file
        if data.get("values") is not None and (
            data.get("_postman_variable_scope") == "environment" or "name" in data
        ):
            return True
        return False

    def parse_environment(self, raw: Any) -> dict[str, str]:
        data = _as_dict(raw) or {}
        out: dict[str, str] = {}
        values = data.get("values")
        if not isinstance(values, list):
            return out
        for row in values:
            if not isinstance(row, dict):
                continue
            if row.get("enabled") is False:
                continue
            key = str(row.get("key") or "").strip()
            if not key:
                continue
            val = row.get("value")
            out[key] = "" if val is None else str(val)
        return out

    def parse_collection(self, raw: Any, *, service: str) -> AmImportBundle:
        data = _as_dict(raw) or {}
        info = data.get("info") if isinstance(data.get("info"), dict) else {}
        label = str(info.get("name") or "postman-import").strip() or "postman-import"
        warnings: list[str] = []
        items: list[AmImportItem] = []
        self._walk_items(data.get("item") or [], items, warnings, prefix="")
        # Collection-level variables as soft env
        env: dict[str, str] = {}
        for row in data.get("variable") or []:
            if isinstance(row, dict) and row.get("key"):
                env[str(row["key"])] = "" if row.get("value") is None else str(row["value"])
        return AmImportBundle(
            source=self.format_id,
            service=service,
            label=label,
            env=env,
            items=items,
            warnings=warnings,
        )

    def _walk_items(
        self,
        nodes: Any,
        out: list[AmImportItem],
        warnings: list[str],
        *,
        prefix: str,
    ) -> None:
        if not isinstance(nodes, list):
            return
        for node in nodes:
            if not isinstance(node, dict):
                continue
            name = str(node.get("name") or "").strip()
            children = node.get("item")
            if isinstance(children, list):
                self._walk_items(children, out, warnings, prefix=f"{prefix}{name}/" if name else prefix)
                continue
            req = node.get("request")
            if req is None:
                warnings.append(f"skip item without request: {prefix}{name or '?'}")
                continue
            if isinstance(req, str):
                method, path, query, headers, body = "GET", req, {}, {}, None
            elif isinstance(req, dict):
                method = str(req.get("method") or "GET").upper()
                path, query = _url_parts(req.get("url"))
                headers = _headers(req.get("header"))
                body = _body(req.get("body"))
            else:
                warnings.append(f"skip unsupported request shape: {prefix}{name or '?'}")
                continue
            if not path:
                warnings.append(f"skip empty path: {prefix}{name or '?'}")
                continue
            display = f"{prefix}{name}" if name else path
            api_id = slug_api_id(method, path, display)
            # Avoid collisions
            existing = {i.api_id for i in out}
            base = api_id
            n = 2
            while api_id in existing:
                api_id = f"{base}.{n}"
                n += 1
            out.append(
                AmImportItem(
                    api_id=api_id,
                    name=display or path,
                    method=method,
                    path=path if path.startswith("/") else f"/{path}",
                    path_params={},
                    query=query,
                    headers=headers,
                    body=body,
                )
            )


def _as_dict(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode("utf-8")
        except Exception:
            return None
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except Exception:
            return None
    return None


def _url_parts(url: Any) -> tuple[str, dict[str, Any]]:
    query: dict[str, Any] = {}
    if isinstance(url, str):
        parsed = urlparse(url)
        path = parsed.path or url
        for k, vals in parse_qs(parsed.query).items():
            query[k] = vals[0] if vals else ""
        return path, query
    if not isinstance(url, dict):
        return "", {}
    raw = url.get("raw")
    if isinstance(raw, str) and raw.strip():
        return _url_parts(raw)
    path_parts = url.get("path")
    if isinstance(path_parts, list):
        segs = [str(p).strip("/") for p in path_parts if str(p).strip()]
        path = "/" + "/".join(segs) if segs else "/"
    else:
        path = str(url.get("path") or "/")
        if not path.startswith("/"):
            path = "/" + path
    for q in url.get("query") or []:
        if isinstance(q, dict) and q.get("key") and q.get("disabled") is not True:
            query[str(q["key"])] = "" if q.get("value") is None else str(q["value"])
    return path, query


def _headers(header: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not isinstance(header, list):
        return out
    for h in header:
        if not isinstance(h, dict):
            continue
        if h.get("disabled") is True:
            continue
        key = str(h.get("key") or "").strip()
        if not key:
            continue
        out[key] = "" if h.get("value") is None else str(h["value"])
    return out


def _body(body: Any) -> Any:
    if not isinstance(body, dict):
        return None
    mode = str(body.get("mode") or "")
    if mode == "raw":
        raw = body.get("raw")
        if isinstance(raw, str):
            text = raw.strip()
            if not text:
                return None
            try:
                return json.loads(text)
            except Exception:
                return text
        return raw
    if mode == "urlencoded":
        out: dict[str, Any] = {}
        for row in body.get("urlencoded") or []:
            if isinstance(row, dict) and row.get("key") and row.get("disabled") is not True:
                out[str(row["key"])] = "" if row.get("value") is None else str(row["value"])
        return out or None
    if mode == "formdata":
        out = {}
        for row in body.get("formdata") or []:
            if isinstance(row, dict) and row.get("key") and row.get("disabled") is not True:
                if row.get("type") == "file":
                    continue
                out[str(row["key"])] = "" if row.get("value") is None else str(row["value"])
        return out or None
    return None
