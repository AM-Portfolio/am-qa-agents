"""Index await skip path."""

import os

import pytest

os.environ["QA_AGENT_SKIP_INDEX_AWAIT"] = "true"


@pytest.mark.asyncio
async def test_await_index_skip():
    from adapters.code_intelligence import await_code_intelligence_index

    r = await await_code_intelligence_index(
        repo="am/am-market",
        branch="feature/x",
        head_sha="abc",
        gnx_mcp_url="http://127.0.0.1:4747",
    )
    assert r["gnx_mode"] == "skipped"
    assert r["skipped"] is True
    assert r["mode"] == "skipped"
    assert r["sync_owner"] == "code-intelligence"
