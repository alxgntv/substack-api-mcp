# Substack API MCP

Substack does **not** provide a native public API for publishing posts.

Authors who want to draft, publish, and schedule from AI agents (Cursor, Claude, and other MCP hosts) were stuck in the browser editor. So we built this MCP server — a posting API for Substack authors, powered by [API Substack](https://apisubstack.com/).

Connect your agent. Publish to Substack.

**Will not start without a valid `APISUBSTACK_API_KEY` (`ask_*`). Get API key here: [apisubstack.com](https://apisubstack.com/).**

> STDIO transport: this server logs to **stderr** only (never stdout), per MCP guidance.

## Why this exists

| Reality | What we built |
|---|---|
| No official Substack write/publish API for authors | A posting MCP so agents can create drafts, publish now, and schedule |
| Authors live in the browser editor | Authors publish through their agents instead |
| Session-cookie auth is the practical path today | `substack.sid` + your publication URL, gated by an API Substack key |

## Examples

- [Alex Ign](https://substack.com/@ignalex) — [ignalex.substack.com](https://ignalex.substack.com/)

## Tools

| Tool | Description |
|---|---|
| `test_connection` | Verify `substack.sid` and return profile |
| `create_post` | Create draft / publish now / schedule (+ optional tags) |
| `get_draft` | Fetch draft by id |
| `update_draft` | Update draft fields |
| `publish_post` | Publish existing draft |
| `schedule_post` | Schedule existing draft |
| `delete_draft` | Delete draft |
| `list_tags` | List publication tags |
| `create_tag` | Create tag |
| `set_tags` | Ensure + attach tags |
| `get_post_tags` | List tags on a post/draft |

## Install

```bash
cd /path/to/Substack-API-MCP
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Auth env

1. Sign in at [apisubstack.com](https://apisubstack.com/), start the free trial, generate an `ask_*` API key.
2. Copy your Substack `substack.sid` cookie.
3. Export:

```bash
export APISUBSTACK_API_KEY="ask_YOUR_KEY"
export SUBSTACK_PUBLICATION_URL="https://yourname.substack.com"
export SUBSTACK_SID="YOUR_SUBSTACK_SID_VALUE"
# optional
# export SUBSTACK_USER_ID="123456"
```

Without `APISUBSTACK_API_KEY`, the process exits immediately (license check against `GET https://rest.apisubstack.com/api/v1/keys/verify`).

## Run

```bash
substack-api-mcp
# or
python -m substack_api_mcp
```

## Cursor / Claude Desktop config

See `mcp.example.json`:

```json
{
  "mcpServers": {
    "substack-api": {
      "command": "/ABSOLUTE/PATH/TO/Substack-API-MCP/.venv/bin/substack-api-mcp",
      "args": [],
      "env": {
        "APISUBSTACK_API_KEY": "ask_YOUR_KEY",
        "SUBSTACK_PUBLICATION_URL": "https://yourname.substack.com",
        "SUBSTACK_SID": "YOUR_SUBSTACK_SID_VALUE"
      }
    }
  }
}
```

Use absolute paths. Restart the host after config changes.

## License

Use at your own risk. Not affiliated with Substack. Built so authors can publish through their agents when Substack itself does not offer a native publishing API.
