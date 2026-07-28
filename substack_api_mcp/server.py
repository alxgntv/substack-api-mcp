# ─── Ariadne's Thread [AT-0001] ─────────────────────
# What: Standalone Substack MCP server project using FastMCP stdio
# Why: Separate MCP packaging from the Python SDK/CLI client per official MCP server guide
# Date: 2026-07-28
# Related: github.com/alxgntv/substack-api-client, modelcontextprotocol.io/docs/develop/build-server
# ─────────────────────────────────────────────────────

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP
from substack_api_client import SubstackAPIError, utc_iso
from substack_api_client.config import build_client

# STDIO servers must not write to stdout (corrupts JSON-RPC). Log to stderr only.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("substack_api_mcp")

mcp = FastMCP(
    "substack-api",
    instructions=(
        "Unofficial Substack post MCP server powered by https://apisubstack.com/. "
        "Requires env SUBSTACK_PUBLICATION_URL and SUBSTACK_SID. "
        "Create drafts, publish, schedule, tag, and delete posts on any publication."
    ),
)


def _ok(payload: Any) -> str:
    logger.info("_ok type=%s", type(payload).__name__)
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _err(exc: Exception) -> str:
    logger.error("_err %s", exc)
    body: dict[str, Any] = {"error": str(exc)}
    if isinstance(exc, SubstackAPIError):
        body["status_code"] = exc.status_code
        body["payload"] = exc.payload
    return json.dumps(body, ensure_ascii=False, indent=2, default=str)


def _client(
    publication_url: str | None = None,
    sid: str | None = None,
    user_id: int | None = None,
):
    logger.info(
        "_client publication_url_set=%s sid_set=%s user_id=%s",
        bool(publication_url),
        bool(sid),
        user_id,
    )
    return build_client(
        publication_url=publication_url,
        sid=sid,
        user_id=user_id,
    )


@mcp.tool()
def test_connection(
    publication_url: str | None = None,
    sid: str | None = None,
    user_id: int | None = None,
) -> str:
    """Verify auth cookie and return basic profile for the configured publication."""
    logger.info("tool.test_connection")
    try:
        client = _client(publication_url, sid, user_id)
        profile = client.get_profile_self()
        return _ok(
            {
                "ok": True,
                "publication_url": client.publication_url,
                "user_id": profile.get("id"),
                "name": profile.get("name"),
                "handle": profile.get("handle"),
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def create_post(
    title: str,
    body: str,
    subtitle: str = "",
    audience: str = "everyone",
    section_id: int | None = None,
    tags: list[str] | None = None,
    send_email: bool = True,
    draft_only: bool = False,
    schedule_at: str | None = None,
    publication_url: str | None = None,
    sid: str | None = None,
    user_id: int | None = None,
) -> str:
    """Create a Substack post as draft, publish now, or schedule. Body is plain text or ProseMirror JSON."""
    logger.info(
        "tool.create_post title=%r draft_only=%s schedule_at=%s tags=%s",
        title,
        draft_only,
        schedule_at,
        tags,
    )
    try:
        client = _client(publication_url, sid, user_id)
        text = body or f"Post created at {utc_iso()}"
        result = client.create_post(
            title=title,
            subtitle=subtitle,
            body=text,
            audience=audience,
            section_id=section_id,
            should_send_email=send_email,
            schedule_at=schedule_at,
            publish=not draft_only and not schedule_at,
            tags=tags,
        )
        return _ok(result)
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def get_draft(
    draft_id: int,
    publication_url: str | None = None,
    sid: str | None = None,
    user_id: int | None = None,
) -> str:
    """Fetch a draft/post by numeric id."""
    logger.info("tool.get_draft draft_id=%s", draft_id)
    try:
        client = _client(publication_url, sid, user_id)
        return _ok(client.get_draft(draft_id))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def update_draft(
    draft_id: int,
    title: str | None = None,
    body: str | None = None,
    subtitle: str | None = None,
    audience: str | None = None,
    section_id: int | None = None,
    send_email: bool | None = None,
    publication_url: str | None = None,
    sid: str | None = None,
    user_id: int | None = None,
) -> str:
    """Update fields on an existing draft."""
    logger.info("tool.update_draft draft_id=%s", draft_id)
    try:
        client = _client(publication_url, sid, user_id)
        return _ok(
            client.update_draft(
                draft_id,
                title=title,
                subtitle=subtitle,
                body=body,
                audience=audience,
                section_id=section_id,
                should_send_email=send_email,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def publish_post(
    draft_id: int,
    audience: str = "everyone",
    send_email: bool = True,
    publication_url: str | None = None,
    sid: str | None = None,
    user_id: int | None = None,
) -> str:
    """Publish an existing draft immediately."""
    logger.info("tool.publish_post draft_id=%s", draft_id)
    try:
        client = _client(publication_url, sid, user_id)
        return _ok(
            client.publish_now(
                draft_id,
                send_email=send_email,
                audience=audience,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def schedule_post(
    draft_id: int,
    schedule_at: str,
    audience: str = "everyone",
    publication_url: str | None = None,
    sid: str | None = None,
    user_id: int | None = None,
) -> str:
    """Schedule an existing draft. schedule_at must be ISO-8601 UTC, e.g. 2026-07-27T08:40:00.000Z."""
    logger.info("tool.schedule_post draft_id=%s schedule_at=%s", draft_id, schedule_at)
    try:
        client = _client(publication_url, sid, user_id)
        result = client.schedule_release(
            draft_id,
            trigger_at=schedule_at,
            post_audience=audience,
            email_audience=audience,
        )
        return _ok(
            {
                "status": "scheduled",
                "draft_id": draft_id,
                "schedule_at": schedule_at,
                "result": result,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def delete_draft(
    draft_id: int,
    publication_url: str | None = None,
    sid: str | None = None,
    user_id: int | None = None,
) -> str:
    """Delete a draft by id."""
    logger.info("tool.delete_draft draft_id=%s", draft_id)
    try:
        client = _client(publication_url, sid, user_id)
        return _ok(client.delete_draft(draft_id))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def list_tags(
    publication_url: str | None = None,
    sid: str | None = None,
    user_id: int | None = None,
) -> str:
    """List all tags configured for the publication."""
    logger.info("tool.list_tags")
    try:
        client = _client(publication_url, sid, user_id)
        return _ok(client.list_post_tags())
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def create_tag(
    name: str,
    publication_url: str | None = None,
    sid: str | None = None,
    user_id: int | None = None,
) -> str:
    """Create a publication tag by name."""
    logger.info("tool.create_tag name=%r", name)
    try:
        client = _client(publication_url, sid, user_id)
        return _ok(client.create_post_tag(name))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def set_tags(
    post_id: int,
    tags: list[str],
    publication_url: str | None = None,
    sid: str | None = None,
    user_id: int | None = None,
) -> str:
    """Ensure tag names exist and attach them to a draft/post."""
    logger.info("tool.set_tags post_id=%s tags=%s", post_id, tags)
    try:
        client = _client(publication_url, sid, user_id)
        return _ok(client.set_post_tags(post_id, tags))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def get_post_tags(
    post_id: int,
    publication_url: str | None = None,
    sid: str | None = None,
    user_id: int | None = None,
) -> str:
    """List tags currently attached to a draft/post."""
    logger.info("tool.get_post_tags post_id=%s", post_id)
    try:
        client = _client(publication_url, sid, user_id)
        return _ok(client.get_post_tags(post_id))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def main() -> None:
    logger.info("starting Substack API MCP server over stdio")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
