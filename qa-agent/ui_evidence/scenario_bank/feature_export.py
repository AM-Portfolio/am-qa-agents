"""Export scenario bank rows to structured feature docs in DB (optional file view)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from ui_evidence.scenario_bank.repo import get_repo, norm_env


def scenarios_to_feature_docs(
    scenarios: list[dict[str, Any]],
    *,
    service_key: str,
    env: str,
    max_per_skill: int = 8,
) -> list[dict[str, Any]]:
    by_skill: dict[str, list[dict[str, Any]]] = {}
    for row in scenarios:
        if row.get("seed") and not row.get("llm_invented"):
            continue
        by_skill.setdefault(str(row.get("skill") or "unknown"), []).append(row)

    docs: list[dict[str, Any]] = []
    for skill, rows in sorted(by_skill.items()):
        for row in rows[:max_per_skill]:
            steps_out: list[dict[str, Any]] = []
            for st in (row.get("steps") or [])[:8]:
                if not isinstance(st, dict):
                    continue
                steps_out.append(
                    {
                        "method": (st.get("method") or "get").upper(),
                        "path": st.get("path") or "",
                        "body_present": st.get("body") is not None and st.get("body") != "",
                        "expected_status": st.get("expected_status"),
                    }
                )
            dedupe = str(row.get("dedupe_key") or row.get("id") or f"{skill}-{len(docs)}")
            docs.append(
                {
                    "feature_id": dedupe,
                    "dedupe_key": dedupe,
                    "service_key": service_key,
                    "env": norm_env(env),
                    "skill": skill,
                    "title": str(row.get("title") or dedupe),
                    "status": row.get("status"),
                    "auth": str(row.get("auth") or "user_jwt"),
                    "negative": bool(row.get("negative")),
                    "tags": [
                        f"@skill:{skill}",
                        f"@{row.get('status')}",
                        "@generated",
                        "@scenario_bank",
                    ]
                    + (["@negative"] if row.get("negative") else []),
                    "steps": steps_out,
                    "gherkin_lines": _gherkin_lines(row),
                }
            )
    return docs


def _gherkin_lines(row: dict[str, Any]) -> list[str]:
    skill = str(row.get("skill") or "unknown")
    title = str(row.get("title") or row.get("dedupe_key") or skill)
    status = row.get("status")
    auth = str(row.get("auth") or "user_jwt")
    lines = [
        f"  @skill:{skill} @{status}",
    ]
    if row.get("negative"):
        lines.append("  @negative")
    lines.append(f"  Scenario: {title}")
    lines.append(f"    Given auth is {auth}")
    steps = row.get("steps") or []
    if not steps:
        lines.append("    When no steps (draft)")
    else:
        for i, st in enumerate(steps[:8]):
            if not isinstance(st, dict):
                continue
            m = (st.get("method") or "get").upper()
            p = st.get("path") or ""
            kw = "When" if i == 0 else "And"
            lines.append(f"    {kw} {m} {p}")
            if st.get("body") is not None and st.get("body") != "":
                lines.append("    And request body is present")
            exp = st.get("expected_status")
            if exp is not None:
                try:
                    lines.append(f"    Then status is {int(exp)}")
                except (TypeError, ValueError):
                    lines.append(f"    Then status is {exp}")
    lines.append(f"    Then scenario status is {status}")
    return lines


def persist_features_from_bank(
    service_key: str,
    env: str,
    *,
    max_per_skill: int = 8,
    export_path: Optional[Path] = None,
    feature_title: str = "Invented bank scenarios",
) -> dict[str, Any]:
    """Write feature docs to repo; optionally render a debug .feature file."""
    env_n = norm_env(env)
    repo = get_repo()
    scenarios = repo.list_scenarios(service_key, env_n)
    docs = scenarios_to_feature_docs(
        scenarios,
        service_key=service_key,
        env=env_n,
        max_per_skill=max_per_skill,
    )
    stored = repo.replace_features(service_key, env_n, docs)
    out: dict[str, Any] = {
        "ok": True,
        "count": stored.get("count", len(docs)),
        "backend": stored.get("backend"),
        "features": docs,
    }
    if export_path is not None:
        path = export_features_file(
            docs,
            export_path,
            feature_title=feature_title,
            service_key=service_key,
        )
        out["export_path"] = str(path)
    return out


def export_features_file(
    feature_docs: list[dict[str, Any]],
    out_path: Path,
    *,
    feature_title: str = "Invented bank scenarios",
    service_key: str = "",
    header_note: str = "Generated from DB scenarios (debug view). SoT is qa_features collection.",
    tags: Optional[list[str]] = None,
) -> Path:
    skills = sorted({str(d.get("skill") or "") for d in feature_docs if d.get("skill")})
    tag_line = " ".join(tags or ["@generated", "@scenario_bank", "@db"])
    lines = [f"# {header_note}", tag_line]
    for skill in skills:
        lines.append(f"@skill:{skill}")
    title = feature_title
    if service_key:
        title = f"{service_key}: {feature_title}"
    lines.append(f"Feature: {title}")
    lines.append("  Scenarios served from Mongo/memory qa_features.")
    lines.append("")
    for doc in feature_docs:
        g = doc.get("gherkin_lines") or []
        lines.extend(g)
        lines.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


# Back-compat name used by older runner/tests
def export_features_from_bank(
    scenarios: list[dict[str, Any]],
    out_path: Path,
    *,
    feature_title: str = "Invented bank scenarios",
    header_note: str = "Generated from scenario bank invent.",
    max_per_skill: int = 8,
    tags: Optional[list[str]] = None,
) -> Path:
    docs = scenarios_to_feature_docs(
        scenarios,
        service_key="",
        env="dev",
        max_per_skill=max_per_skill,
    )
    return export_features_file(
        docs,
        out_path,
        feature_title=feature_title,
        header_note=header_note,
        tags=tags,
    )
