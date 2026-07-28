# ─── Ariadne's Thread [AT-0010] ─────────────────────
# What: Gate MCP on live APISUBSTACK_API_KEY via rest.apisubstack.com verify
# Why: Refuse to start/run tools without a key from https://apisubstack.com/
# Date: 2026-07-28
# Related: [AT-0007] substack_api_mcp/server.py, rest.apisubstack.com/api/v1/keys/verify
# ─────────────────────────────────────────────────────

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

import requests

logger = logging.getLogger("substack_api_mcp.license")

DEFAULT_API_BASE = "https://rest.apisubstack.com"
VERIFY_PATH = "/api/v1/keys/verify"
CACHE_TTL_SECONDS = 300.0

_lock = threading.Lock()
_cached_until = 0.0
_cached_payload: dict[str, Any] | None = None


class ApisubstackLicenseError(RuntimeError):
    """Raised when APISUBSTACK_API_KEY is missing or rejected."""


def _api_base() -> str:
    return (os.getenv("APISUBSTACK_API_BASE") or DEFAULT_API_BASE).rstrip("/")


def get_apisubstack_api_key() -> str:
    key = (os.getenv("APISUBSTACK_API_KEY") or "").strip()
    logger.info(
        "get_apisubstack_api_key: set=%s prefix=%s",
        bool(key),
        key[:12] if key else None,
    )
    if not key:
        raise ApisubstackLicenseError(
            "APISUBSTACK_API_KEY is required. Generate a key at https://apisubstack.com/"
        )
    if not key.startswith("ask_"):
        raise ApisubstackLicenseError(
            "APISUBSTACK_API_KEY must be an ask_* key from https://apisubstack.com/"
        )
    return key


def _verify_remote(api_key: str) -> dict[str, Any]:
    url = f"{_api_base()}{VERIFY_PATH}"
    logger.info("verify_remote: GET %s", url)
    try:
        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "User-Agent": "substack-api-mcp/0.1.0",
            },
            timeout=20.0,
        )
    except requests.RequestException as exc:
        logger.error("verify_remote: network error %s", exc)
        raise ApisubstackLicenseError(
            f"Failed to reach API Substack license server ({url}): {exc}"
        ) from exc

    logger.info(
        "verify_remote: status=%s bytes=%s",
        response.status_code,
        len(response.content or b""),
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": (response.text or "")[:500]}

    if response.status_code == 401:
        raise ApisubstackLicenseError(
            "Invalid or revoked APISUBSTACK_API_KEY. Generate a key at https://apisubstack.com/"
        )
    if response.status_code == 402:
        raise ApisubstackLicenseError(
            "Subscription inactive for this API key. Start or renew at https://apisubstack.com/"
        )
    if response.status_code >= 400 or not isinstance(payload, dict) or not payload.get("ok"):
        raise ApisubstackLicenseError(
            f"APISUBSTACK_API_KEY verification failed HTTP {response.status_code}: {payload}"
        )
    logger.info(
        "verify_remote: ok keyPrefix=%s subscriptionStatus=%s",
        payload.get("keyPrefix"),
        payload.get("subscriptionStatus"),
    )
    return payload


def require_apisubstack_license(*, force: bool = False) -> dict[str, Any]:
    """
    Require a valid APISUBSTACK_API_KEY from https://apisubstack.com/.

    Uses a short in-process cache to avoid hammering verify on every tool call.
    Cache updates are serialized with a lock (no concurrent corrupt state).
    """
    global _cached_until, _cached_payload

    now = time.monotonic()
    if not force:
        with _lock:
            if _cached_payload is not None and now < _cached_until:
                logger.info(
                    "require_apisubstack_license: cache hit until_in=%.1fs",
                    _cached_until - now,
                )
                return dict(_cached_payload)

    api_key = get_apisubstack_api_key()
    payload = _verify_remote(api_key)

    with _lock:
        _cached_payload = dict(payload)
        _cached_until = time.monotonic() + CACHE_TTL_SECONDS
        logger.info(
            "require_apisubstack_license: cached for %ss keyPrefix=%s",
            CACHE_TTL_SECONDS,
            payload.get("keyPrefix"),
        )
        return dict(_cached_payload)
