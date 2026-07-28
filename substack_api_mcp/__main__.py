# ─── Ariadne's Thread [AT-0003] ─────────────────────
# What: Module entrypoint for STDIO MCP server
# Why: Support `python -m substack_api_mcp` like official MCP quickstart
# Date: 2026-07-28
# Related: [AT-0001] substack_api_mcp/server.py:main
# ─────────────────────────────────────────────────────

from .server import main

if __name__ == "__main__":
    main()
