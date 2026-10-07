"""Unit tests for LiteLLM probe (no live network)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from ui_evidence.scenario_bank.llm_status import probe_litellm


def test_probe_missing_key():
    with patch.dict("os.environ", {"LITELLM_MASTER_KEY": "", "OPENAI_API_KEY": ""}, clear=False):
        # Force empty via explicit api_key
        out = probe_litellm(api_key="", base_url="http://litellm.test")
    assert out["available"] is False
    assert out["provider"] == "litellm"
    assert out["key_configured"] is False
    assert "unset" in (out.get("error") or "")


def test_probe_models_ok():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [{"id": "deepseek-chat"}, {"id": "gpt-4o-mini"}]
    }
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_resp

    with patch("ui_evidence.scenario_bank.llm_status.httpx.Client", return_value=mock_client):
        out = probe_litellm(
            api_key="sk-test",
            base_url="http://litellm.test",
            ping_chat=False,
        )
    assert out["available"] is True
    assert out["models_count"] == 2
    assert "deepseek-chat" in out["models_sample"]
    assert "key" not in out
    assert out.get("error") is None


def test_probe_chat_fail_marks_unavailable():
    models_resp = MagicMock()
    models_resp.status_code = 200
    models_resp.json.return_value = {"data": [{"id": "deepseek-chat"}]}
    chat_resp = MagicMock()
    chat_resp.status_code = 500
    chat_resp.text = "boom"

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = models_resp
    mock_client.post.return_value = chat_resp

    with patch("ui_evidence.scenario_bank.llm_status.httpx.Client", return_value=mock_client):
        out = probe_litellm(
            api_key="sk-test",
            base_url="http://litellm.test",
            model="deepseek-chat",
            ping_chat=True,
        )
    assert out["available"] is False
    assert "chat HTTP 500" in (out.get("error") or "")
