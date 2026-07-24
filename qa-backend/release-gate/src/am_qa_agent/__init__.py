"""Legacy shim — packages live at repo root (gateway, orchestrator, …)."""
from composition.identity import AGENT_ID, DISPLAY_NAME, __version__
__all__ = ["AGENT_ID", "DISPLAY_NAME", "__version__"]
