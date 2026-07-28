# Substack API MCP

Standalone [Model Context Protocol](https://modelcontextprotocol.io/docs/develop/build-server) server for Substack posts.

Built with the official Python FastMCP SDK (`mcp[cli]`). Powered by [API Substack](https://apisubstack.com/).

Self-contained Substack posting client. **Will not start without a valid `APISUBSTACK_API_KEY` (`ask_*`) from [apisubstack.com](https://apisubstack.com/).**

> STDIO transport: this server logs to **stderr** only (never stdout), per MCP guidance.

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

Use at your own risk. Not affiliated with Substack.
