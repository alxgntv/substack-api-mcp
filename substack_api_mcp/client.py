# ─── Ariadne's Thread [AT-0006] ─────────────────────
# What: Vendor Substack client into MCP package (standalone, no external SDK)
# Why: MCP must be a self-contained Substack posting product
# Date: 2026-07-28
# Related: [AT-0005] substack_api_mcp/config.py, [AT-0001] substack_api_mcp/server.py
# ─────────────────────────────────────────────────────
# ─── Ariadne's Thread [AT-0019] ─────────────────────
# What: Implement universal Substack post-create API client from recorded traffic
# Why: Publish posts on any publication using only draft create/update/publish/schedule calls
# Date: 2026-07-26
# Related: [AT-0018] substack_api_mcp/body.py:ensure_draft_body, recordings→POST /api/v1/drafts
# ─────────────────────────────────────────────────────
"""
Minimal Substack publish sequence (from capture, trash removed):

1. POST   {publication}/api/v1/drafts
2. PUT    {publication}/api/v1/drafts/{id}
3a. GET   {publication}/api/v1/drafts/{id}/prepublish?publish_date=...
    POST  {publication}/api/v1/drafts/{id}/scheduled_release   (schedule)
3b. POST  {publication}/api/v1/drafts/{id}/publish             (publish now)

Auth header required: Cookie: substack.sid=<session>
Optional: user_id for draft_bylines (auto-fetched from substack.com profile/self)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests

from .body import ensure_draft_body

logger = logging.getLogger("substack_api_mcp.client")

GLOBAL_API = "https://substack.com/api/v1"


@dataclass
class SubstackAuth:
    """Browser session auth for Substack unofficial API."""

    session_cookie: str
    user_id: int | None = None

    def cookie_header(self) -> str:
        raw = (self.session_cookie or "").strip()
        if not raw:
            raise ValueError("session_cookie is empty")
        if "substack.sid=" in raw:
            logger.info("cookie_header: using provided Cookie string as-is")
            return raw
        value = f"substack.sid={raw}"
        logger.info("cookie_header: wrapped raw sid value")
        return value


class SubstackAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class SubstackClient:
    """Universal Substack post client for any publication URL / subdomain."""

    def __init__(
        self,
        publication_url: str,
        auth: SubstackAuth,
        timeout: float = 30.0,
        user_agent: str = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/150.0.0.0 Safari/537.36"
        ),
    ) -> None:
        self.publication_url = self._normalize_publication_url(publication_url)
        self.auth = auth
        self.timeout = timeout
        self.user_agent = user_agent
        self.session = requests.Session()
        logger.info(
            "SubstackClient.init: publication_url=%s timeout=%s user_id=%s",
            self.publication_url,
            self.timeout,
            self.auth.user_id,
        )

    @staticmethod
    def _normalize_publication_url(url: str) -> str:
        raw = (url or "").strip().rstrip("/")
        if not raw:
            raise ValueError("publication_url is required")
        if not raw.startswith("http://") and not raw.startswith("https://"):
            raw = "https://" + raw
        parsed = urlparse(raw)
        if not parsed.netloc:
            raise ValueError(f"Invalid publication_url: {url!r}")
        normalized = f"{parsed.scheme}://{parsed.netloc}"
        logger.info("normalize_publication_url: %s -> %s", url, normalized)
        return normalized

    def _api_url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        url = f"{self.publication_url}/api/v1{path}"
        logger.info("_api_url: %s", url)
        return url

    def _headers(self, *, referer: str | None = None, json_body: bool = False) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Cookie": self.auth.cookie_header(),
            "Origin": self.publication_url,
            "Referer": referer or f"{self.publication_url}/publish",
            "User-Agent": self.user_agent,
        }
        if json_body:
            headers["Content-Type"] = "application/json"
        logger.info(
            "_headers: keys=%s referer=%s json_body=%s",
            list(headers.keys()),
            headers["Referer"],
            json_body,
        )
        return headers

    def _request(
        self,
        method: str,
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        referer: str | None = None,
        allow_empty: bool = False,
    ) -> Any:
        logger.info(
            "_request: %s %s params=%s body_keys=%s",
            method,
            url,
            list((params or {}).keys()),
            list((json_body or {}).keys()),
        )
        response = self.session.request(
            method=method.upper(),
            url=url,
            headers=self._headers(referer=referer, json_body=json_body is not None),
            json=json_body,
            params=params,
            timeout=self.timeout,
        )
        logger.info(
            "_request: status=%s content_type=%s bytes=%s",
            response.status_code,
            response.headers.get("Content-Type"),
            len(response.content or b""),
        )
        if response.status_code in (401, 403):
            raise SubstackAPIError(
                "Auth failed (401/403). Provide a fresh substack.sid cookie.",
                status_code=response.status_code,
                payload=self._safe_json(response),
            )
        if response.status_code >= 400:
            raise SubstackAPIError(
                f"Substack API error HTTP {response.status_code}: {response.text[:500]}",
                status_code=response.status_code,
                payload=self._safe_json(response),
            )
        if allow_empty and not (response.content or b"").strip():
            logger.info("_request: empty body accepted")
            return None
        if not (response.content or b"").strip():
            logger.info("_request: empty body, returning None")
            return None
        try:
            payload = response.json()
        except ValueError as exc:
            raise SubstackAPIError(
                f"Non-JSON response HTTP {response.status_code}",
                status_code=response.status_code,
                payload=response.text[:500],
            ) from exc
        logger.info(
            "_request: parsed_type=%s keys=%s",
            type(payload).__name__,
            list(payload.keys()) if isinstance(payload, dict) else None,
        )
        return payload

    @staticmethod
    def _safe_json(response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return response.text[:1000]

    def get_profile_self(self) -> dict[str, Any]:
        """Fetch current user profile (for draft_bylines user id)."""
        url = f"{GLOBAL_API}/user/profile/self"
        logger.info("get_profile_self: GET %s", url)
        payload = self._request(
            "GET",
            url,
            referer="https://substack.com/",
        )
        if not isinstance(payload, dict):
            raise SubstackAPIError("Unexpected profile response", payload=payload)
        logger.info("get_profile_self: id=%s", payload.get("id"))
        return payload

    def resolve_user_id(self) -> int:
        if self.auth.user_id is not None:
            logger.info("resolve_user_id: using provided user_id=%s", self.auth.user_id)
            return int(self.auth.user_id)
        profile = self.get_profile_self()
        user_id = profile.get("id")
        if not user_id:
            raise SubstackAPIError("Could not resolve user_id from profile/self", payload=profile)
        self.auth.user_id = int(user_id)
        logger.info("resolve_user_id: resolved user_id=%s", self.auth.user_id)
        return self.auth.user_id

    def create_draft(
        self,
        *,
        title: str = "",
        subtitle: str = "",
        body: str | dict[str, Any] | None = None,
        audience: str = "everyone",
        post_type: str = "newsletter",
        section_id: int | None = None,
        detect_language: bool = True,
    ) -> dict[str, Any]:
        """Step 1: POST /api/v1/drafts"""
        user_id = self.resolve_user_id()
        payload = {
            "draft_title": title or "",
            "draft_subtitle": subtitle or "",
            "draft_podcast_url": None,
            "draft_podcast_duration": None,
            "draft_body": ensure_draft_body(body),
            "section_chosen": section_id is not None,
            "draft_section_id": section_id,
            "detect_language": detect_language,
            "translations": [],
            "draft_bylines": [{"id": user_id, "is_guest": False}],
            "audience": audience,
            "type": post_type,
        }
        logger.info(
            "create_draft: title_len=%s audience=%s type=%s section_id=%s",
            len(title or ""),
            audience,
            post_type,
            section_id,
        )
        result = self._request(
            "POST",
            self._api_url("/drafts"),
            json_body=payload,
            referer=f"{self.publication_url}/publish/post?type={post_type}",
        )
        if not isinstance(result, dict) or "id" not in result:
            raise SubstackAPIError("create_draft failed: missing id", payload=result)
        logger.info(
            "create_draft: ok id=%s publication_id=%s draft_updated_at=%s",
            result.get("id"),
            result.get("publication_id"),
            result.get("draft_updated_at"),
        )
        return result

    def get_draft(self, draft_id: int | str) -> dict[str, Any]:
        """GET /api/v1/drafts/{id}"""
        logger.info("get_draft: id=%s", draft_id)
        result = self._request(
            "GET",
            self._api_url(f"/drafts/{draft_id}"),
            referer=f"{self.publication_url}/publish/post/{draft_id}",
        )
        if not isinstance(result, dict):
            raise SubstackAPIError("get_draft failed", payload=result)
        return result

    def update_draft(
        self,
        draft_id: int | str,
        *,
        title: str | None = None,
        subtitle: str | None = None,
        body: str | dict[str, Any] | None = None,
        audience: str | None = None,
        section_id: int | None = None,
        should_send_email: bool | None = None,
        write_comment_permissions: str | None = None,
        cover_image: str | None = None,
        last_updated_at: str | None = None,
        detect_language: bool = False,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Step 2: PUT /api/v1/drafts/{id}"""
        user_id = self.resolve_user_id()
        if last_updated_at is None:
            current = self.get_draft(draft_id)
            last_updated_at = current.get("draft_updated_at")
            logger.info("update_draft: fetched last_updated_at=%s", last_updated_at)

        payload: dict[str, Any] = {
            "draft_bylines": [{"id": user_id, "is_guest": False}],
            "detect_language": detect_language,
            "translations": [],
            "last_updated_at": last_updated_at,
        }
        if title is not None:
            payload["draft_title"] = title
        if subtitle is not None:
            payload["draft_subtitle"] = subtitle
        if body is not None:
            payload["draft_body"] = ensure_draft_body(body)
        if audience is not None:
            payload["audience"] = audience
        if section_id is not None:
            payload["draft_section_id"] = section_id
            payload["section_chosen"] = True
        else:
            payload.setdefault("section_chosen", False)
            payload.setdefault("draft_section_id", None)
        if should_send_email is not None:
            payload["should_send_email"] = should_send_email
        if write_comment_permissions is not None:
            payload["write_comment_permissions"] = write_comment_permissions
        if cover_image is not None:
            payload["cover_image"] = cover_image
        if extra:
            payload.update(extra)

        logger.info(
            "update_draft: id=%s keys=%s",
            draft_id,
            list(payload.keys()),
        )
        result = self._request(
            "PUT",
            self._api_url(f"/drafts/{draft_id}"),
            json_body=payload,
            referer=f"{self.publication_url}/publish/post/{draft_id}",
        )
        if not isinstance(result, dict):
            raise SubstackAPIError("update_draft failed", payload=result)
        logger.info(
            "update_draft: ok id=%s draft_updated_at=%s title=%s",
            result.get("id"),
            result.get("draft_updated_at"),
            result.get("draft_title"),
        )
        return result

    def prepublish(self, draft_id: int | str, publish_date: str) -> dict[str, Any]:
        """Step 3a helper: GET /api/v1/drafts/{id}/prepublish?publish_date=..."""
        logger.info("prepublish: id=%s publish_date=%s", draft_id, publish_date)
        result = self._request(
            "GET",
            self._api_url(f"/drafts/{draft_id}/prepublish"),
            params={"publish_date": publish_date},
            referer=f"{self.publication_url}/publish/post/{draft_id}",
        )
        if not isinstance(result, dict):
            raise SubstackAPIError("prepublish failed", payload=result)
        errors = result.get("errors") or []
        logger.info("prepublish: errors=%s suggestions=%s", errors, result.get("suggestions"))
        if errors:
            raise SubstackAPIError("prepublish returned errors", payload=result)
        return result

    def schedule_release(
        self,
        draft_id: int | str,
        *,
        trigger_at: str,
        post_audience: str = "everyone",
        email_audience: str = "everyone",
        run_prepublish: bool = True,
    ) -> Any:
        """Step 3a: POST /api/v1/drafts/{id}/scheduled_release (from capture)."""
        logger.info(
            "schedule_release: id=%s trigger_at=%s post_audience=%s email_audience=%s",
            draft_id,
            trigger_at,
            post_audience,
            email_audience,
        )
        if run_prepublish:
            self.prepublish(draft_id, trigger_at)
        payload = {
            "trigger_at": trigger_at,
            "post_audience": post_audience,
            "email_audience": email_audience,
        }
        result = self._request(
            "POST",
            self._api_url(f"/drafts/{draft_id}/scheduled_release"),
            json_body=payload,
            referer=f"{self.publication_url}/publish/post/{draft_id}",
            allow_empty=True,
        )
        logger.info("schedule_release: done result=%s", result)
        return result

    def publish_now(
        self,
        draft_id: int | str,
        *,
        send_email: bool = True,
        audience: str = "everyone",
        share_automatically: bool = False,
    ) -> dict[str, Any]:
        """Step 3b: POST /api/v1/drafts/{id}/publish (immediate publish)."""
        payload = {
            "send": send_email,
            "share_automatically": share_automatically,
            "audience": audience,
        }
        logger.info("publish_now: id=%s payload=%s", draft_id, payload)
        result = self._request(
            "POST",
            self._api_url(f"/drafts/{draft_id}/publish"),
            json_body=payload,
            referer=f"{self.publication_url}/publish/post/{draft_id}",
        )
        if not isinstance(result, dict):
            raise SubstackAPIError("publish_now failed", payload=result)
        logger.info(
            "publish_now: ok id=%s slug=%s is_published=%s",
            result.get("id"),
            result.get("slug"),
            result.get("is_published"),
        )
        return result

    # ─── Ariadne's Thread [AT-0022] ─────────────────────
    # What: Add publication post-tag list/create/attach APIs
    # Why: Attach tags to drafts/posts using captured Substack tag endpoints
    # Date: 2026-07-26
    # Related: [AT-0019] substack_api_mcp/client.py:SubstackClient, recordings→/api/v1/publication/post-tag
    # ─────────────────────────────────────────────────────
    def list_post_tags(self) -> list[dict[str, Any]]:
        """GET /api/v1/publication/post-tag"""
        logger.info("list_post_tags: start")
        result = self._request(
            "GET",
            self._api_url("/publication/post-tag"),
            referer=f"{self.publication_url}/publish",
        )
        if not isinstance(result, list):
            raise SubstackAPIError("list_post_tags failed", payload=result)
        logger.info("list_post_tags: count=%s", len(result))
        return result

    def get_post_tags(self, post_id: int | str) -> list[dict[str, Any]]:
        """GET /api/v1/post/{id}/tag"""
        logger.info("get_post_tags: post_id=%s", post_id)
        result = self._request(
            "GET",
            self._api_url(f"/post/{post_id}/tag"),
            referer=f"{self.publication_url}/publish/post/{post_id}",
        )
        if not isinstance(result, list):
            raise SubstackAPIError("get_post_tags failed", payload=result)
        logger.info("get_post_tags: count=%s", len(result))
        return result

    def create_post_tag(self, name: str) -> dict[str, Any]:
        """POST /api/v1/publication/post-tag  body: {name}"""
        logger.info("create_post_tag: name=%r", name)
        result = self._request(
            "POST",
            self._api_url("/publication/post-tag"),
            json_body={"name": name},
            referer=f"{self.publication_url}/publish",
        )
        if not isinstance(result, dict) or "id" not in result:
            raise SubstackAPIError("create_post_tag failed", payload=result)
        logger.info("create_post_tag: id=%s slug=%s", result.get("id"), result.get("slug"))
        return result

    def attach_post_tag(self, post_id: int | str, tag_id: str) -> dict[str, Any]:
        """POST /api/v1/post/{id}/tag/{tag_id}"""
        logger.info("attach_post_tag: post_id=%s tag_id=%s", post_id, tag_id)
        result = self._request(
            "POST",
            self._api_url(f"/post/{post_id}/tag/{tag_id}"),
            json_body={},
            referer=f"{self.publication_url}/publish/post/{post_id}",
        )
        if not isinstance(result, dict):
            raise SubstackAPIError("attach_post_tag failed", payload=result)
        logger.info("attach_post_tag: ok %s", result)
        return result

    def ensure_tags(self, names: list[str]) -> list[dict[str, Any]]:
        """Resolve tag names to tag objects, creating missing ones."""
        logger.info("ensure_tags: names=%s", names)
        existing = self.list_post_tags()
        by_name = {str(t.get("name", "")).strip().lower(): t for t in existing}
        resolved: list[dict[str, Any]] = []
        for name in names:
            key = name.strip().lower()
            if not key:
                continue
            tag = by_name.get(key)
            if tag is None:
                logger.info("ensure_tags: creating missing tag %r", name)
                tag = self.create_post_tag(name.strip())
                by_name[key] = tag
            resolved.append(tag)
        logger.info("ensure_tags: resolved=%s", [t.get("name") for t in resolved])
        return resolved

    def set_post_tags(self, post_id: int | str, tag_names: list[str]) -> list[dict[str, Any]]:
        """Ensure tags exist and attach them to the post/draft."""
        logger.info("set_post_tags: post_id=%s tag_names=%s", post_id, tag_names)
        tags = self.ensure_tags(tag_names)
        attached: list[dict[str, Any]] = []
        current = self.get_post_tags(post_id)
        current_ids = {
            str(item.get("post_tag_id") or item.get("id") or "")
            for item in current
        }
        for tag in tags:
            tag_id = str(tag.get("id"))
            if tag_id in current_ids:
                logger.info("set_post_tags: already attached tag_id=%s name=%s", tag_id, tag.get("name"))
                attached.append({"tag": tag, "status": "already_attached"})
                continue
            link = self.attach_post_tag(post_id, tag_id)
            attached.append({"tag": tag, "link": link, "status": "attached"})
        logger.info("set_post_tags: done count=%s", len(attached))
        return attached

    def delete_draft(self, draft_id: int | str) -> dict[str, Any]:
        # ─── Ariadne's Thread [AT-0023] ─────────────────────
        # What: Add DELETE /api/v1/drafts/{id}
        # Why: Allow removing drafts created by the client
        # Date: 2026-07-26
        # Related: [AT-0019] substack_api_mcp/client.py:SubstackClient.create_draft
        # ─────────────────────────────────────────────────────
        logger.info("delete_draft: id=%s", draft_id)
        result = self._request(
            "DELETE",
            self._api_url(f"/drafts/{draft_id}"),
            referer=f"{self.publication_url}/publish/post/{draft_id}",
            allow_empty=True,
        )
        logger.info("delete_draft: done id=%s result=%s", draft_id, result)
        return {"status": "deleted", "draft_id": draft_id, "response": result or {}}

    def create_post(
        self,
        *,
        title: str,
        body: str | dict[str, Any],
        subtitle: str = "",
        audience: str = "everyone",
        section_id: int | None = None,
        should_send_email: bool = True,
        schedule_at: str | None = None,
        publish: bool = True,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Full universal flow to create (and optionally publish/schedule) a post.

        schedule_at: ISO-8601 UTC datetime string for scheduled_release.
        publish: if True and schedule_at is None -> publish immediately.
        """
        logger.info(
            "create_post: title=%r publish=%s schedule_at=%s audience=%s section_id=%s tags=%s",
            title,
            publish,
            schedule_at,
            audience,
            section_id,
            tags,
        )
        created = self.create_draft(
            title=title,
            subtitle=subtitle,
            body=body,
            audience=audience,
            section_id=section_id,
        )
        draft_id = created["id"]
        updated = self.update_draft(
            draft_id,
            title=title,
            subtitle=subtitle,
            body=body,
            audience=audience,
            section_id=section_id,
            should_send_email=should_send_email,
            write_comment_permissions="everyone",
            last_updated_at=created.get("draft_updated_at"),
            extra={
                "draft_podcast_url": None,
                "draft_podcast_duration": None,
                "audience_before_archived": None,
                "syndicate_voiceover_to_rss": False,
                "syndicate_to_section_id": None,
                "should_syndicate_to_other_feed": None,
                "default_comment_sort": None,
                "meter_type": "none",
                "cover_image": None,
                "search_engine_title": None,
                "search_engine_description": None,
            },
        )

        outcome: dict[str, Any] = {
            "draft_id": draft_id,
            "draft": updated,
            "publication_url": self.publication_url,
            "edit_url": f"{self.publication_url}/publish/post/{draft_id}",
        }

        if tags:
            outcome["tags"] = self.set_post_tags(draft_id, tags)

        if schedule_at:
            self.schedule_release(
                draft_id,
                trigger_at=schedule_at,
                post_audience=audience,
                email_audience=audience,
            )
            outcome["status"] = "scheduled"
            outcome["schedule_at"] = schedule_at
            logger.info("create_post: scheduled draft_id=%s at=%s", draft_id, schedule_at)
            return outcome

        if publish:
            published = self.publish_now(
                draft_id,
                send_email=should_send_email,
                audience=audience,
            )
            slug = published.get("slug")
            outcome["status"] = "published"
            outcome["post"] = published
            outcome["url"] = f"{self.publication_url}/p/{slug}" if slug else None
            logger.info("create_post: published draft_id=%s url=%s", draft_id, outcome["url"])
            return outcome

        outcome["status"] = "draft"
        logger.info("create_post: left as draft draft_id=%s", draft_id)
        return outcome


def utc_iso(dt: datetime | None = None) -> str:
    value = dt or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    text = value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    logger.info("utc_iso: %s", text)
    return text
