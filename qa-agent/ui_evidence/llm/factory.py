from __future__ import annotations

import logging

from ui_evidence.config import settings
from ui_evidence.llm.base import LLMClient
from ui_evidence.llm.gateway_client import GatewayLLMClient
from ui_evidence.llm.litellm_client import LiteLLMClient

logger = logging.getLogger(__name__)


def create_llm_client() -> LLMClient:
    if settings.llm_routing == "direct":
        logger.info(
            "LLM routing=direct → %s (dev fast path; Langfuse via LiteLLM callback only)",
            settings.LITELLM_BASE_URL,
        )
        return LiteLLMClient()

    logger.info(
        "LLM routing=gateway → %s → %s",
        settings.MCP_GATEWAY_BASE_URL,
        settings.LITELLM_BASE_URL,
    )
    return GatewayLLMClient()
