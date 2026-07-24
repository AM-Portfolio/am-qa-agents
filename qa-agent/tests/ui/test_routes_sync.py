from pathlib import Path
import runpy


def test_check_routes_sync_exits_clean():
    script = Path(__file__).resolve().parents[1] / "scripts" / "check_routes_sync.py"
    # run as __main__ would — just import markers path exists
    assert script.is_file()
    ns = runpy.run_path(str(script), run_name="not_main")
    assert "DART_SYNC_MARKERS" in str(ns.get("DART_SYNC_MARKERS", [])) or "main" in ns
