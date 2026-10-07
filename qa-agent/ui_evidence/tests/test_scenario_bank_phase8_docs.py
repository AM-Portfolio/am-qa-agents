"""Phase 8 — UI profiles + docs env wording."""
from __future__ import annotations

from pathlib import Path

from ui_evidence.plugins import loader as plugin_loader


def test_subscription_ui_profiles_include_sub_ui():
    plugin_loader.reload_plugins()
    p = plugin_loader.get_plugin(plugin_id="am-subscription")
    assert p is not None
    profiles = plugin_loader.load_ui_profiles(p)
    assert "SUB_UI_OPEN" in profiles
    assert "SUB_UI_PLANS" in profiles
    assert any(x.startswith("SUB_UI_") for x in profiles)


def test_feature_stubs_exist_with_skill_tags():
    root = Path(__file__).resolve().parents[2] / "plugins"
    sub = (root / "am-subscription" / "features").glob("*.feature")
    texts = [p.read_text(encoding="utf-8") for p in sub]
    assert texts
    assert any("@skill:" in t for t in texts)


def test_scenario_bank_docs_no_bare_dig_env():
    """Refuse env wording 'dig' except explicit never-dig / normalize notes."""
    docs = Path(__file__).resolve().parents[3] / "docs" / "qa-agent" / "scenario-bank"
    allowed_fragments = (
        "never dig",
        "not dig",
        'input `dig`',
        "input dig",
        "`dig` →",
        "`dig` normalized",
        "no env \"dig\"",
        "no bare \"dig\"",
        "grep dig",
        "Saying **dig**",
        "(never dig)",
        "use dig as the mutate env",
        "dig` normalized",
        "bare dig",
        "no bare dig",
    )
    bad: list[str] = []
    for path in docs.rglob("*"):
        if path.suffix.lower() not in {".md", ".drawio"}:
            continue
        text = path.read_text(encoding="utf-8")
        lower = text.lower()
        if "dig" not in lower:
            continue
        # strip allowed meta lines then flag remaining dig as env labels
        for i, line in enumerate(text.splitlines(), 1):
            ll = line.lower()
            if "dig" not in ll:
                continue
            if any(a.lower() in ll for a in allowed_fragments):
                continue
            if "st_dig" in ll:  # draw.io cell id
                continue
            bad.append(f"{path.name}:{i}:{line.strip()[:100]}")
    assert not bad, "bare dig env wording:\n" + "\n".join(bad)
