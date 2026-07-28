# ─── Ariadne's Thread [AT-0018] ─────────────────────
# What: Build ProseMirror draft_body helpers for Substack posts
# Why: Substack API expects draft_body as JSON string of a ProseMirror doc
# Date: 2026-07-26
# Related: [AT-0019] substack_api_mcp/client.py:SubstackClient.create_post
# ─────────────────────────────────────────────────────

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("substack_api_mcp.body")


def empty_doc() -> dict[str, Any]:
    logger.info("empty_doc: building empty ProseMirror document")
    return {"type": "doc", "content": [{"type": "paragraph", "attrs": {"textAlign": None}}]}


def paragraph(text: str, link: str | None = None) -> dict[str, Any]:
    logger.info("paragraph: text_len=%s link=%s", len(text or ""), bool(link))
    if not text:
        return {"type": "paragraph", "attrs": {"textAlign": None}}
    node: dict[str, Any] = {"type": "text", "text": text}
    if link:
        node["marks"] = [
            {
                "type": "link",
                "attrs": {
                    "href": link,
                    "target": "_blank",
                    "rel": "noopener noreferrer nofollow",
                    "class": None,
                },
            }
        ]
    return {"type": "paragraph", "attrs": {"textAlign": None}, "content": [node]}


def plain_text_to_doc(text: str) -> dict[str, Any]:
    """Convert plain text (newline-separated paragraphs) to ProseMirror doc."""
    logger.info("plain_text_to_doc: input_len=%s", len(text or ""))
    lines = (text or "").split("\n")
    content: list[dict[str, Any]] = []
    for line in lines:
        content.append(paragraph(line))
    if not content:
        content = [paragraph("")]
    doc = {"type": "doc", "content": content}
    logger.info("plain_text_to_doc: paragraphs=%s", len(content))
    return doc


def ensure_draft_body(body: str | dict[str, Any] | None) -> str:
    """Return draft_body as JSON string expected by Substack API."""
    logger.info("ensure_draft_body: input_type=%s", type(body).__name__)
    if body is None:
        raw = empty_doc()
    elif isinstance(body, dict):
        raw = body
    elif isinstance(body, str):
        stripped = body.strip()
        if stripped.startswith("{") and '"type"' in stripped:
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, dict) and parsed.get("type") == "doc":
                    logger.info("ensure_draft_body: accepted ProseMirror JSON string")
                    return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
            except json.JSONDecodeError:
                logger.info("ensure_draft_body: not JSON, treating as plain text")
        raw = plain_text_to_doc(body)
    else:
        raise TypeError(f"Unsupported draft body type: {type(body)!r}")

    encoded = json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
    logger.info("ensure_draft_body: encoded_len=%s", len(encoded))
    return encoded
