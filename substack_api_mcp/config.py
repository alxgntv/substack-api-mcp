# ─── Ariadne's Thread [AT-0005] ─────────────────────
# What: Env/auth helpers for standalone MCP Substack client
# Why: MCP package must not depend on external substack-api-client
# Date: 2026-07-28
# Related: [AT-0001] substack_api_mcp/server.py, substack_api_mcp/client.py:SubstackClient
# ─────────────────────────────────────────────────────

from __future__ import annotations

import logging
import os

from .client import SubstackAuth, SubstackClient

logger = logging.getLogger("substack_api_mcp.config")


def env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    logger.info("env: %s set=%s", name, bool(value))
    return value


def build_client(
    *,
    publication_url: str | None = None,
    sid: str | None = None,
    user_id: int | None = None,
) -> SubstackClient:
    pub = (publication_url or env("SUBSTACK_PUBLICATION_URL")).strip()
    cookie = (sid or env("SUBSTACK_SID")).strip()
    if not pub:
        raise ValueError("publication_url is required (arg or SUBSTACK_PUBLICATION_URL)")
    if not cookie:
        raise ValueError("sid is required (arg or SUBSTACK_SID)")
    uid_raw = env("SUBSTACK_USER_ID")
    resolved_uid = user_id
    if resolved_uid is None and uid_raw:
        resolved_uid = int(uid_raw)
    logger.info(
        "build_client: publication_url=%s user_id=%s",
        pub,
        resolved_uid,
    )
    return SubstackClient(
        publication_url=pub,
        auth=SubstackAuth(session_cookie=cookie, user_id=resolved_uid),
    )
