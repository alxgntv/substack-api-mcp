# ─── Ariadne's Thread [AT-0002] ─────────────────────
# What: Export MCP package public surface
# Why: Allow `python -m substack_api_mcp` and installable entrypoint
# Date: 2026-07-28
# Related: [AT-0001] substack_api_mcp/server.py
# ─────────────────────────────────────────────────────

from .server import main, mcp

__all__ = ["main", "mcp"]
