from pathlib import Path

from app.target_loader import get_target_config


def test_local_targets_have_domain_profiles():
    path = (
        Path(__file__).resolve().parents[2]
        / "am-modern-ui"
        / "testing"
        / "targets.local.json"
    )
    if not path.is_file():
        # workspace layout: am-agents/../am-modern-ui
        path = Path(__file__).resolve().parents[3] / "am-modern-ui" / "testing" / "targets.local.json"
    if not path.is_file():
        return
    dash = get_target_config(path, target_name="dashboard")
    assert dash.profile == "DASHBOARD_SMOKE_FLOW"
    port = get_target_config(path, target_name="portfolio")
    assert port.profile == "PORTFOLIO_SMOKE_FLOW"
    assert port.persona == "demo_user"
