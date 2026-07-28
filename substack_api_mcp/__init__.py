# ─── Ariadne's Thread [AT-0008] ─────────────────────
# What: Export MCP package public surface including vendored client
# Why: Allow `python -m substack_api_mcp` and installable entrypoint
# Date: 2026-07-28
# Related: [AT-0007] substack_api_mcp/server.py, [AT-0006] substack_api_mcp/client.py
# ─────────────────────────────────────────────────────

from .client import SubstackAPIError, SubstackAuth, SubstackClient, utc_iso
from .server import main, mcp

__all__ = [
    "SubstackAPIError",
    "SubstackAuth",
    "SubstackClient",
    "main",
    "mcp",
    "utc_iso",
]
