"""CI provenance helpers — survive k6 finalize + list projection."""

from specs.ci_provenance import extract_ci_provenance, merge_ci_provenance


def test_extract_from_dict_skips_empty():
    got = extract_ci_provenance(
        {
            "git_ref": "main",
            "git_sha": "abc123",
            "committer_name": "ssd2658",
            "commit_message": "",
            "github_run_url": "https://github.com/AM-Portfolio/am-market/actions/runs/1",
            "unrelated": "x",
        }
    )
    assert got == {
        "git_ref": "main",
        "git_sha": "abc123",
        "committer_name": "ssd2658",
        "github_run_url": "https://github.com/AM-Portfolio/am-market/actions/runs/1",
    }


def test_merge_restores_wiped_run_params():
    record = {
        "triggered_by": "ci-main",
        "payloads_used": {
            "run_params": {"profile": "load", "triggered_by": "ci-main"},
        },
    }
    prov = {
        "git_ref": "main",
        "committer_name": "ssd2658",
        "trigger_source": "github_actions",
        "github_run_id": "38084661947",
    }
    merge_ci_provenance(record, prov)
    assert record["git_ref"] == "main"
    assert record["committer_name"] == "ssd2658"
    rp = record["payloads_used"]["run_params"]
    assert rp["git_ref"] == "main"
    assert rp["github_run_id"] == "38084661947"
    assert rp["profile"] == "load"
