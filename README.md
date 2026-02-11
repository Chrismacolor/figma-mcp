# Figma MCP Server

MCP server that lets Claude create and edit Figma designs through natural language — bridges Claude (MCP/stdio) to a Figma plugin (HTTP polling) via a single Python process.

## Architecture

```
Claude Desktop ──[MCP/stdio]──► Python Server ◄──[HTTP/localhost:8300]──► Figma Plugin
                                (single process)                          (polls every 1.5s)
                                ├─ MCP tool handler
                                ├─ FastAPI HTTP routes
                                └─ In-memory job queue
```

## Setup

### 1. Python Server

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "figma": {
      "command": "/path/to/figma-mcp/.venv/bin/figma-mcp",
      "env": {
        "FIGMA_MCP_TOKEN": "your-stable-token-here"
      }
    }
  }
}
```

Setting `FIGMA_MCP_TOKEN` gives you a stable auth token across restarts. If omitted, a random token is generated each time and printed to stderr.

### 3. Figma Plugin

```bash
cd plugin
npm install
npm run build
```

In Figma: **Plugins → Development → Import plugin from manifest** → select `plugin/manifest.json`.

Open the plugin, paste your auth token, and click **Connect**. Keep the plugin panel open while using Claude.

<img width="1432" height="959" alt="Screenshot 2026-02-10 at 8 44 20 AM" src="https://github.com/user-attachments/assets/4c976e47-89eb-40b1-bcde-e5eb338e7e80" />

## MCP Tools

| Tool | Description |
|------|-------------|
| `enqueue_ops` | Send a batch of design operations to Figma |
| `get_job_status` | Check if a job completed, failed, or is still pending |
| `read_node_tree` | Read the current Figma page structure (waits up to 30s for plugin) |
| `list_jobs` | List all jobs and their statuses |

## Ops DSL

Each op requires a unique `tempId` and an `op` type: `CREATE_FRAME`, `CREATE_RECTANGLE`, `CREATE_ELLIPSE`, or `CREATE_TEXT`.

### Parent Referencing

- `parentTempId` — reference a node declared earlier in the **same batch**
- `parentNodeId` — reference a real Figma node ID (e.g. `"16:2"`) from a **previous batch's** result, enabling cross-batch nesting

### Example

```json
[
  {"op": "CREATE_FRAME", "tempId": "hero", "name": "Hero", "w": 1440, "h": 900,
   "layoutMode": "VERTICAL", "primaryAxisAlignItems": "CENTER",
   "fills": [{"r": 0.1, "g": 0.1, "b": 0.15}]},

  {"op": "CREATE_TEXT", "tempId": "h1", "parentTempId": "hero",
   "text": "Welcome", "fontSize": 64, "fontWeight": 700,
   "fills": [{"r": 1, "g": 1, "b": 1}]}
]
```

### Font Weights

Accepts both string and numeric values:

| Numeric | String |
|---------|--------|
| 100 | Thin |
| 200 | Extra Light |
| 300 | Light |
| 400 | Regular |
| 500 | Medium |
| 600 | Semi Bold |
| 700 | Bold |
| 800 | Extra Bold |
| 900 | Black |

### Op Field Reference

**All ops:** `tempId`, `parentTempId`, `parentNodeId`, `name`, `x`, `y`, `fills [{r,g,b,a}]`

**CREATE_FRAME:** `w`, `h`, `cornerRadius`, `layoutMode`, `itemSpacing`, `paddingLeft/Right/Top/Bottom`, `primaryAxisAlignItems`, `counterAxisAlignItems`, `clipsContent`

**CREATE_RECTANGLE:** `w`, `h`, `cornerRadius`, `opacity`

**CREATE_ELLIPSE:** `w`, `h`, `opacity`

**CREATE_TEXT:** `text`, `fontSize`, `fontFamily`, `fontWeight`, `textAlignHorizontal`, `textAutoResize`, `w`, `h`, `lineHeight`, `letterSpacing`, `opacity`
