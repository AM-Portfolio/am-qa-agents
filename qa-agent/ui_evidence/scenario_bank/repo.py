"""Scenario-bank repository — Mongo SoT with in-memory backend for tests."""
from __future__ import annotations

import logging
import os
import time
import uuid
from copy import deepcopy
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)

COL_SPECS = "qa_specs"
COL_SURFACE = "qa_api_surface"
COL_PROFILES = "qa_invent_profiles"
COL_SCENARIOS = "qa_scenarios"
COL_FEATURES = "qa_features"
COL_KNOWLEDGE = "qa_knowledge"
COL_LOCKS = "qa_invent_locks"
COL_META = "qa_bank_meta"


def norm_env(env: str) -> str:
    e = (env or "dev").strip().lower()
    return "dev" if e == "dig" else e


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class BankRepo(Protocol):
    def get_meta(self, service_key: str, env: str) -> dict[str, Any]: ...
    def set_meta(self, service_key: str, env: str, patch: dict[str, Any]) -> dict[str, Any]: ...
    def list_scenarios(self, service_key: str, env: str) -> list[dict[str, Any]]: ...
    def upsert_scenario(
        self, service_key: str, env: str, row: dict[str, Any], *, cap: int
    ) -> dict[str, Any]: ...
    def clear_llm_invented(self, service_key: str, env: str) -> dict[str, Any]: ...
    def replace_scenarios(
        self, service_key: str, env: str, scenarios: list[dict[str, Any]]
    ) -> None: ...
    def upsert_spec(self, doc: dict[str, Any]) -> dict[str, Any]: ...
    def get_spec(
        self, service_key: str, env: str, *, source: str = "tools"
    ) -> dict[str, Any]: ...
    def upsert_surface(self, service_key: str, env: str, doc: dict[str, Any]) -> dict[str, Any]: ...
    def get_surface(self, service_key: str, env: str) -> dict[str, Any]: ...
    def upsert_profile(self, service_key: str, env: str, doc: dict[str, Any]) -> dict[str, Any]: ...
    def get_profile(self, service_key: str, env: str) -> dict[str, Any]: ...
    def replace_features(
        self, service_key: str, env: str, features: list[dict[str, Any]]
    ) -> dict[str, Any]: ...
    def list_features(self, service_key: str, env: str) -> list[dict[str, Any]]: ...
    def upsert_knowledge(self, service_key: str, env: str, doc: dict[str, Any]) -> dict[str, Any]: ...
    def get_knowledge(self, service_key: str, env: str) -> dict[str, Any]: ...
    def acquire_lock(
        self, service_key: str, env: str, *, owner: str, ttl: int
    ) -> dict[str, Any]: ...
    def release_lock(self, service_key: str, env: str, *, owner: str) -> dict[str, Any]: ...


class MemoryBankRepo:
    """Process-local store used for unit tests and Mongo-unavailable fallback."""

    def __init__(self) -> None:
        self._meta: dict[str, dict[str, Any]] = {}
        self._scenarios: dict[str, list[dict[str, Any]]] = {}
        self._specs: dict[str, dict[str, Any]] = {}
        self._surface: dict[str, dict[str, Any]] = {}
        self._profiles: dict[str, dict[str, Any]] = {}
        self._features: dict[str, list[dict[str, Any]]] = {}
        self._knowledge: dict[str, dict[str, Any]] = {}
        self._locks: dict[str, dict[str, Any]] = {}

    def _sk(self, service_key: str, env: str) -> str:
        return f"{service_key}|{norm_env(env)}"

    def reset(self) -> None:
        self.__init__()

    def get_meta(self, service_key: str, env: str) -> dict[str, Any]:
        k = self._sk(service_key, env)
        base = self._meta.get(k) or {
            "service_key": service_key,
            "env": norm_env(env),
            "invent_complete": False,
            "needs_reinvent": False,
        }
        return deepcopy(base)

    def set_meta(self, service_key: str, env: str, patch: dict[str, Any]) -> dict[str, Any]:
        k = self._sk(service_key, env)
        cur = self.get_meta(service_key, env)
        cur.update(patch)
        cur["service_key"] = service_key
        cur["env"] = norm_env(env)
        cur["updated_at"] = _now()
        self._meta[k] = cur
        return deepcopy(cur)

    def list_scenarios(self, service_key: str, env: str) -> list[dict[str, Any]]:
        return deepcopy(self._scenarios.get(self._sk(service_key, env)) or [])

    def replace_scenarios(
        self, service_key: str, env: str, scenarios: list[dict[str, Any]]
    ) -> None:
        self._scenarios[self._sk(service_key, env)] = deepcopy(scenarios)

    def upsert_scenario(
        self, service_key: str, env: str, row: dict[str, Any], *, cap: int
    ) -> dict[str, Any]:
        scenarios = self.list_scenarios(service_key, env)
        dedupe = str(row.get("dedupe_key") or row.get("id") or "")
        if not dedupe:
            dedupe = f"auto-{uuid.uuid4().hex[:12]}"
            row = {**row, "dedupe_key": dedupe}
        if "id" not in row:
            row = {**row, "id": dedupe}
        replaced = False
        for i, existing in enumerate(scenarios):
            if str(existing.get("dedupe_key") or existing.get("id")) == dedupe:
                scenarios[i] = {**existing, **row, "dedupe_key": dedupe}
                replaced = True
                break
        if not replaced:
            scenarios.append(dict(row))
        while len(scenarios) > cap:
            drop_i = next(
                (i for i, s in enumerate(scenarios) if not s.get("seed")),
                0,
            )
            scenarios.pop(drop_i)
        self.replace_scenarios(service_key, env, scenarios)
        self.set_meta(service_key, env, {"updated_at": _now()})
        return {
            "ok": True,
            "replaced": replaced,
            "count": len(scenarios),
            "dedupe_key": dedupe,
            "backend": "memory",
        }

    def clear_llm_invented(self, service_key: str, env: str) -> dict[str, Any]:
        before = self.list_scenarios(service_key, env)
        kept = [s for s in before if not s.get("llm_invented")]
        self.replace_scenarios(service_key, env, kept)
        self.set_meta(
            service_key,
            env,
            {"invent_complete": False, "needs_reinvent": True},
        )
        return {
            "ok": True,
            "removed": len(before) - len(kept),
            "kept": len(kept),
            "backend": "memory",
        }

    def upsert_spec(self, doc: dict[str, Any]) -> dict[str, Any]:
        sk = str(doc.get("service_key") or "")
        env = norm_env(str(doc.get("env") or "dev"))
        source = str(doc.get("source") or "tools")
        key = f"{sk}|{env}|{source}"
        payload = {**doc, "env": env, "updated_at": _now()}
        self._specs[key] = payload
        return deepcopy(payload)

    def get_spec(
        self, service_key: str, env: str, *, source: str = "tools"
    ) -> dict[str, Any]:
        return deepcopy(
            self._specs.get(f"{service_key}|{norm_env(env)}|{source}") or {}
        )

    def upsert_surface(
        self, service_key: str, env: str, doc: dict[str, Any]
    ) -> dict[str, Any]:
        k = self._sk(service_key, env)
        payload = {
            **doc,
            "service_key": service_key,
            "env": norm_env(env),
            "updated_at": _now(),
        }
        self._surface[k] = payload
        return deepcopy(payload)

    def get_surface(self, service_key: str, env: str) -> dict[str, Any]:
        return deepcopy(self._surface.get(self._sk(service_key, env)) or {})

    def upsert_profile(
        self, service_key: str, env: str, doc: dict[str, Any]
    ) -> dict[str, Any]:
        k = self._sk(service_key, env)
        payload = {
            **doc,
            "service_key": service_key,
            "env": norm_env(env),
            "updated_at": _now(),
        }
        self._profiles[k] = payload
        return deepcopy(payload)

    def get_profile(self, service_key: str, env: str) -> dict[str, Any]:
        return deepcopy(self._profiles.get(self._sk(service_key, env)) or {})

    def replace_features(
        self, service_key: str, env: str, features: list[dict[str, Any]]
    ) -> dict[str, Any]:
        rows = []
        for f in features:
            fid = str(f.get("feature_id") or f.get("dedupe_key") or uuid.uuid4().hex[:12])
            rows.append(
                {
                    **f,
                    "feature_id": fid,
                    "service_key": service_key,
                    "env": norm_env(env),
                    "updated_at": _now(),
                }
            )
        self._features[self._sk(service_key, env)] = rows
        return {"ok": True, "count": len(rows), "backend": "memory"}

    def list_features(self, service_key: str, env: str) -> list[dict[str, Any]]:
        return deepcopy(self._features.get(self._sk(service_key, env)) or [])

    def upsert_knowledge(
        self, service_key: str, env: str, doc: dict[str, Any]
    ) -> dict[str, Any]:
        k = self._sk(service_key, env)
        cur = self.get_knowledge(service_key, env)
        cur.update(doc)
        cur["service_key"] = service_key
        cur["env"] = norm_env(env)
        cur["updated_at"] = _now()
        self._knowledge[k] = cur
        return deepcopy(cur)

    def get_knowledge(self, service_key: str, env: str) -> dict[str, Any]:
        return deepcopy(self._knowledge.get(self._sk(service_key, env)) or {})

    def acquire_lock(
        self, service_key: str, env: str, *, owner: str, ttl: int
    ) -> dict[str, Any]:
        k = self._sk(service_key, env)
        now = time.time()
        existing = self._locks.get(k)
        if existing and float(existing.get("expires_at") or 0) > now:
            return {
                "ok": False,
                "held": True,
                "owner": existing.get("owner"),
                "expires_at": existing.get("expires_at"),
            }
        owner_id = owner or f"pid-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        payload = {
            "owner": owner_id,
            "acquired_at": now,
            "expires_at": now + ttl,
            "service_key": service_key,
            "env": norm_env(env),
        }
        self._locks[k] = payload
        return {"ok": True, "held": False, "owner": owner_id, "expires_at": payload["expires_at"]}

    def release_lock(self, service_key: str, env: str, *, owner: str) -> dict[str, Any]:
        k = self._sk(service_key, env)
        existing = self._locks.get(k)
        if not existing:
            return {"ok": True, "released": False, "reason": "no_lock"}
        if existing.get("owner") != owner:
            return {"ok": False, "released": False, "reason": "not_owner"}
        self._locks.pop(k, None)
        return {"ok": True, "released": True}


class MongoBankRepo:
    """MongoDB persistence for invent/run artifacts."""

    def __init__(self, uri: str, database: str) -> None:
        from pymongo import MongoClient

        self._client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        self._db = self._client[database]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self._db[COL_SCENARIOS].create_index(
            [("service_key", 1), ("env", 1), ("dedupe_key", 1)], unique=True
        )
        self._db[COL_FEATURES].create_index(
            [("service_key", 1), ("env", 1), ("feature_id", 1)], unique=True
        )
        self._db[COL_SURFACE].create_index(
            [("service_key", 1), ("env", 1)], unique=True
        )
        self._db[COL_PROFILES].create_index(
            [("service_key", 1), ("env", 1)], unique=True
        )
        self._db[COL_KNOWLEDGE].create_index(
            [("service_key", 1), ("env", 1)], unique=True
        )
        self._db[COL_META].create_index(
            [("service_key", 1), ("env", 1)], unique=True
        )
        self._db[COL_SPECS].create_index(
            [("service_key", 1), ("env", 1), ("source", 1)], unique=True
        )
        self._db[COL_LOCKS].create_index(
            [("service_key", 1), ("env", 1)], unique=True
        )

    def get_meta(self, service_key: str, env: str) -> dict[str, Any]:
        env_n = norm_env(env)
        doc = self._db[COL_META].find_one(
            {"service_key": service_key, "env": env_n}, {"_id": 0}
        )
        if not doc:
            return {
                "service_key": service_key,
                "env": env_n,
                "invent_complete": False,
                "needs_reinvent": False,
            }
        return dict(doc)

    def set_meta(self, service_key: str, env: str, patch: dict[str, Any]) -> dict[str, Any]:
        env_n = norm_env(env)
        payload = {**patch, "service_key": service_key, "env": env_n, "updated_at": _now()}
        self._db[COL_META].update_one(
            {"service_key": service_key, "env": env_n},
            {"$set": payload},
            upsert=True,
        )
        return self.get_meta(service_key, env_n)

    def list_scenarios(self, service_key: str, env: str) -> list[dict[str, Any]]:
        env_n = norm_env(env)
        cur = self._db[COL_SCENARIOS].find(
            {"service_key": service_key, "env": env_n}, {"_id": 0}
        )
        return list(cur)

    def replace_scenarios(
        self, service_key: str, env: str, scenarios: list[dict[str, Any]]
    ) -> None:
        env_n = norm_env(env)
        self._db[COL_SCENARIOS].delete_many(
            {"service_key": service_key, "env": env_n}
        )
        if not scenarios:
            return
        docs = []
        for s in scenarios:
            docs.append(
                {
                    **s,
                    "service_key": service_key,
                    "env": env_n,
                    "dedupe_key": str(s.get("dedupe_key") or s.get("id") or uuid.uuid4().hex),
                }
            )
        self._db[COL_SCENARIOS].insert_many(docs)

    def upsert_scenario(
        self, service_key: str, env: str, row: dict[str, Any], *, cap: int
    ) -> dict[str, Any]:
        env_n = norm_env(env)
        dedupe = str(row.get("dedupe_key") or row.get("id") or "")
        if not dedupe:
            dedupe = f"auto-{uuid.uuid4().hex[:12]}"
            row = {**row, "dedupe_key": dedupe}
        if "id" not in row:
            row = {**row, "id": dedupe}
        doc = {
            **row,
            "service_key": service_key,
            "env": env_n,
            "dedupe_key": dedupe,
            "updated_at": _now(),
        }
        res = self._db[COL_SCENARIOS].update_one(
            {"service_key": service_key, "env": env_n, "dedupe_key": dedupe},
            {"$set": doc},
            upsert=True,
        )
        # Cap eviction
        count = self._db[COL_SCENARIOS].count_documents(
            {"service_key": service_key, "env": env_n}
        )
        while count > cap:
            victim = self._db[COL_SCENARIOS].find_one(
                {"service_key": service_key, "env": env_n, "seed": {"$ne": True}},
                sort=[("updated_at", 1)],
            )
            if not victim:
                victim = self._db[COL_SCENARIOS].find_one(
                    {"service_key": service_key, "env": env_n},
                    sort=[("updated_at", 1)],
                )
            if not victim:
                break
            self._db[COL_SCENARIOS].delete_one({"_id": victim["_id"]})
            count -= 1
        self.set_meta(service_key, env_n, {"updated_at": _now()})
        return {
            "ok": True,
            "replaced": not bool(res.upserted_id),
            "count": self._db[COL_SCENARIOS].count_documents(
                {"service_key": service_key, "env": env_n}
            ),
            "dedupe_key": dedupe,
            "backend": "mongo",
        }

    def clear_llm_invented(self, service_key: str, env: str) -> dict[str, Any]:
        env_n = norm_env(env)
        before = self._db[COL_SCENARIOS].count_documents(
            {"service_key": service_key, "env": env_n}
        )
        res = self._db[COL_SCENARIOS].delete_many(
            {
                "service_key": service_key,
                "env": env_n,
                "llm_invented": True,
            }
        )
        self.set_meta(
            service_key,
            env_n,
            {"invent_complete": False, "needs_reinvent": True},
        )
        kept = self._db[COL_SCENARIOS].count_documents(
            {"service_key": service_key, "env": env_n}
        )
        return {
            "ok": True,
            "removed": int(res.deleted_count),
            "kept": kept,
            "backend": "mongo",
            "before": before,
        }

    def upsert_spec(self, doc: dict[str, Any]) -> dict[str, Any]:
        sk = str(doc.get("service_key") or "")
        env_n = norm_env(str(doc.get("env") or "dev"))
        source = str(doc.get("source") or "tools")
        payload = {**doc, "service_key": sk, "env": env_n, "source": source, "updated_at": _now()}
        self._db[COL_SPECS].update_one(
            {"service_key": sk, "env": env_n, "source": source},
            {"$set": payload},
            upsert=True,
        )
        return self.get_spec(sk, env_n, source=source)

    def get_spec(
        self, service_key: str, env: str, *, source: str = "tools"
    ) -> dict[str, Any]:
        doc = self._db[COL_SPECS].find_one(
            {
                "service_key": service_key,
                "env": norm_env(env),
                "source": source,
            },
            {"_id": 0},
        )
        return dict(doc or {})

    def upsert_surface(
        self, service_key: str, env: str, doc: dict[str, Any]
    ) -> dict[str, Any]:
        env_n = norm_env(env)
        payload = {
            **doc,
            "service_key": service_key,
            "env": env_n,
            "updated_at": _now(),
        }
        self._db[COL_SURFACE].update_one(
            {"service_key": service_key, "env": env_n},
            {"$set": payload},
            upsert=True,
        )
        return self.get_surface(service_key, env_n)

    def get_surface(self, service_key: str, env: str) -> dict[str, Any]:
        doc = self._db[COL_SURFACE].find_one(
            {"service_key": service_key, "env": norm_env(env)}, {"_id": 0}
        )
        return dict(doc or {})

    def upsert_profile(
        self, service_key: str, env: str, doc: dict[str, Any]
    ) -> dict[str, Any]:
        env_n = norm_env(env)
        payload = {
            **doc,
            "service_key": service_key,
            "env": env_n,
            "updated_at": _now(),
        }
        self._db[COL_PROFILES].update_one(
            {"service_key": service_key, "env": env_n},
            {"$set": payload},
            upsert=True,
        )
        return self.get_profile(service_key, env_n)

    def get_profile(self, service_key: str, env: str) -> dict[str, Any]:
        doc = self._db[COL_PROFILES].find_one(
            {"service_key": service_key, "env": norm_env(env)}, {"_id": 0}
        )
        return dict(doc or {})

    def replace_features(
        self, service_key: str, env: str, features: list[dict[str, Any]]
    ) -> dict[str, Any]:
        env_n = norm_env(env)
        self._db[COL_FEATURES].delete_many(
            {"service_key": service_key, "env": env_n}
        )
        if features:
            docs = []
            for f in features:
                fid = str(
                    f.get("feature_id") or f.get("dedupe_key") or uuid.uuid4().hex[:12]
                )
                docs.append(
                    {
                        **f,
                        "feature_id": fid,
                        "service_key": service_key,
                        "env": env_n,
                        "updated_at": _now(),
                    }
                )
            self._db[COL_FEATURES].insert_many(docs)
        return {"ok": True, "count": len(features), "backend": "mongo"}

    def list_features(self, service_key: str, env: str) -> list[dict[str, Any]]:
        return list(
            self._db[COL_FEATURES].find(
                {"service_key": service_key, "env": norm_env(env)}, {"_id": 0}
            )
        )

    def upsert_knowledge(
        self, service_key: str, env: str, doc: dict[str, Any]
    ) -> dict[str, Any]:
        env_n = norm_env(env)
        cur = self.get_knowledge(service_key, env_n)
        cur.update(doc)
        cur["service_key"] = service_key
        cur["env"] = env_n
        cur["updated_at"] = _now()
        self._db[COL_KNOWLEDGE].update_one(
            {"service_key": service_key, "env": env_n},
            {"$set": cur},
            upsert=True,
        )
        return self.get_knowledge(service_key, env_n)

    def get_knowledge(self, service_key: str, env: str) -> dict[str, Any]:
        doc = self._db[COL_KNOWLEDGE].find_one(
            {"service_key": service_key, "env": norm_env(env)}, {"_id": 0}
        )
        return dict(doc or {})

    def acquire_lock(
        self, service_key: str, env: str, *, owner: str, ttl: int
    ) -> dict[str, Any]:
        env_n = norm_env(env)
        now = time.time()
        existing = self._db[COL_LOCKS].find_one(
            {"service_key": service_key, "env": env_n}
        )
        if existing and float(existing.get("expires_at") or 0) > now:
            return {
                "ok": False,
                "held": True,
                "owner": existing.get("owner"),
                "expires_at": existing.get("expires_at"),
            }
        owner_id = owner or f"pid-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        payload = {
            "owner": owner_id,
            "acquired_at": now,
            "expires_at": now + ttl,
            "service_key": service_key,
            "env": env_n,
        }
        self._db[COL_LOCKS].update_one(
            {"service_key": service_key, "env": env_n},
            {"$set": payload},
            upsert=True,
        )
        return {"ok": True, "held": False, "owner": owner_id, "expires_at": payload["expires_at"]}

    def release_lock(self, service_key: str, env: str, *, owner: str) -> dict[str, Any]:
        env_n = norm_env(env)
        existing = self._db[COL_LOCKS].find_one(
            {"service_key": service_key, "env": env_n}
        )
        if not existing:
            return {"ok": True, "released": False, "reason": "no_lock"}
        if existing.get("owner") != owner:
            return {"ok": False, "released": False, "reason": "not_owner"}
        self._db[COL_LOCKS].delete_one({"service_key": service_key, "env": env_n})
        return {"ok": True, "released": True}


_REPO: Optional[BankRepo] = None
_MEMORY = MemoryBankRepo()
_DIR_TOKEN: Optional[str] = None


def reset_repo_for_tests() -> MemoryBankRepo:
    """Force fresh memory backend (pytest)."""
    global _REPO, _DIR_TOKEN
    _MEMORY.reset()
    _REPO = _MEMORY
    _DIR_TOKEN = os.getenv("QA_SCENARIO_BANK_DIR")
    os.environ["QA_SCENARIO_BANK_BACKEND"] = "memory"
    return _MEMORY


def get_repo() -> BankRepo:
    """Resolve backend: memory when QA_SCENARIO_BANK_DIR set or backend=memory; else Mongo."""
    global _REPO, _DIR_TOKEN

    dir_token = os.getenv("QA_SCENARIO_BANK_DIR")
    # Isolate pytest tmp dirs: new QA_SCENARIO_BANK_DIR → fresh memory
    if dir_token is not None and dir_token != _DIR_TOKEN:
        _DIR_TOKEN = dir_token
        _MEMORY.reset()
        _REPO = _MEMORY
        return _REPO

    if _REPO is not None:
        return _REPO

    backend = (os.getenv("QA_SCENARIO_BANK_BACKEND") or "").strip().lower()
    if not backend:
        if dir_token:
            backend = "memory"
        else:
            backend = "mongo"

    if backend == "memory":
        _REPO = _MEMORY
        return _REPO

    try:
        # Local invent: prefer dig Mongo over localhost defaults
        if not os.getenv("KUBERNETES_SERVICE_HOST"):
            from ui_evidence.scenario_bank.mongo_resolve import (
                ensure_dev_mongo_for_local_invent,
            )

            ensure_dev_mongo_for_local_invent()

        from ui_evidence.config import settings

        uri = os.getenv("MONGO_URI") or settings.MONGO_URI
        db_name = os.getenv("MONGO_DATABASE") or settings.MONGO_DATABASE
        repo = MongoBankRepo(uri, db_name)
        repo._client.admin.command("ping")
        _REPO = repo
        logger.info(
            "scenario_bank repo=mongo db=%s uri_host=%s",
            db_name,
            uri.split("@")[-1].split("/")[0] if "@" in uri else uri[:48],
        )
        return _REPO
    except Exception as exc:  # noqa: BLE001
        logger.warning("Mongo unavailable (%s); using memory bank repo", exc)
        _REPO = _MEMORY
        return _REPO
