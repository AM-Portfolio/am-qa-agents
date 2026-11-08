"""Generate services/*.md review cards from catalog.yaml."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
SPECS = Path(r"f:\am-repos\am-repos\am-specs")

API_GROUPS = {
    "am-market-data": "Quotes/LTP/OHLC, instruments, indices, watchlists, fundamentals, IPO, MF, streaming",
    "am-news": "Current affairs, holdings news, admin feed/replay",
    "am-parser": "Excel/file parse jobs, ETF/MF holdings extraction",
    "am-portfolio": "Portfolios, holdings, baskets, snapshots, stress/what-if",
    "am-analysis": "Allocation, performance, category/entity top movers",
    "am-trade-management-service": "Trades, journals, replays, metrics, heatmaps",
    "am-oms": "Wallets, positions, orders (create/list/cancel/replace)",
    "am-subscription": "Plans, me, usage, referrals, entitlements",
}

GAPS = {
    "am-market-data": "Promote 6 composed flows into durable qa-agent pack; repair onboard openapi_sync flakiness.",
    "am-news": "flows: [] — author health→affairs and holdings news flows.",
    "am-parser": "flows: [] — author upload→poll→holdings; mutating = dig only.",
    "am-portfolio": "flows: [] — author list→holdings→snapshot; UI flows exist only.",
    "am-analysis": "flows: [] — linear 4-op analysis flow; needs portfolio id binds.",
    "am-trade-management-service": "flows: [] — list→detail→journal; replay read paths.",
    "am-oms": "flows: [] — wallet→positions→orders; create/cancel dig-only.",
    "am-subscription": "Plugin pack exists; commit overview/payload fixture; add business.yaml flows.",
}


def main() -> None:
    cat = yaml.safe_load((ROOT / "catalog.yaml").read_text(encoding="utf-8"))
    out_dir = ROOT / "services"
    out_dir.mkdir(parents=True, exist_ok=True)
    for s in cat["services"]:
        sid = s["id"]
        envs = s.get("environments") or {}
        ops = (s.get("openapi") or {}).get("operations")
        dg = s.get("data_gen") or {}
        lines = [
            f"# {sid}",
            "",
            f"- **Domain:** {s.get('domain')}",
            f"- **Status:** {s.get('status')} (enabled={s.get('enabled')})",
            f"- **Priority:** {s.get('priority')}",
            f"- **OpenAPI ops:** {ops}",
            f"- **Snapshot:** `{(s.get('openapi') or {}).get('yaml')}`",
            f"- **Data-gen:** `{dg.get('template_dir')}` (business.yaml={dg.get('business_yaml')})",
            "",
            "## Environment matrix (am-specs targets)",
            "",
            "| Env | Base URL | Feed posture |",
            "|-----|----------|--------------|",
            f"| {'dev'} | `{envs.get('dev')}` | Full feed + mutating OK |",
            f"| preprod | `{envs.get('preprod')}` | Sync + import; prefer read/replay |",
            f"| prod | `{envs.get('prod')}` | Read-only / must-work only |",
            "",
            "## API groups",
            "",
            API_GROUPS.get(sid, "(see OpenAPI)"),
            "",
            "## Gaps / next",
            "",
            GAPS.get(sid, ""),
            "",
        ]
        text = "\n".join(lines)
        (out_dir / f"{sid}.md").write_text(text, encoding="utf-8")
        print("wrote", sid)
    print("done", out_dir)


if __name__ == "__main__":
    main()
