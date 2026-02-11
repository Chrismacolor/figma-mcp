# Figma MCP Server

MCP server that lets Claude create and edit Figma designs through natural language — bridges Claude (MCP/stdio) to a Figma plugin (HTTP polling) via a single Python process.

## Architecture

```
Claude Desktop ──[MCP/stdio]──► Python Server ◄──[HTTP/localhost:8400]──► Figma Plugin
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

## MCP Tools

| Tool | Description |
|------|-------------|
| `enqueue_ops` | Send a batch of design operations to Figma |
| `get_job_status` | Wait for a job to complete (default 15s timeout) and return results |
| `read_node_tree` | Read the current Figma page structure with rich property data |
| `list_jobs` | List all jobs and their statuses |

All tools include plugin connection awareness — they warn if the Figma plugin appears disconnected.

## Ops DSL

Each op requires a unique `tempId` and an `op` type.

### Op Types

| Op | Description |
|----|-------------|
| `CREATE_FRAME` | Create a frame (supports auto-layout, shadows) |
| `CREATE_RECTANGLE` | Create a rectangle |
| `CREATE_ELLIPSE` | Create an ellipse |
| `CREATE_TEXT` | Create a text node |
| `UPDATE_NODE` | Update properties of an existing node by `nodeId` |
| `DELETE_NODE` | Remove an existing node by `nodeId` |

### Parent Referencing

- `parentTempId` — reference a node declared earlier in the **same batch**
- `parentNodeId` — reference a real Figma node ID (e.g. `"16:2"`) from a **previous batch's** result, enabling cross-batch nesting

### Examples

**Create nodes:**
```json
[
  {"op": "CREATE_FRAME", "tempId": "card", "name": "Card", "w": 360, "h": 200,
   "layoutMode": "VERTICAL", "primaryAxisAlignItems": "CENTER",
   "fills": [{"r": 1, "g": 1, "b": 1}],
   "stroke": {"r": 0.9, "g": 0.9, "b": 0.9, "weight": 1},
   "dropShadow": {"color": {"r": 0, "g": 0, "b": 0, "a": 0.1}, "offset": {"x": 0, "y": 2}, "radius": 8}},

  {"op": "CREATE_TEXT", "tempId": "h1", "parentTempId": "card",
   "text": "Hello World", "fontSize": 24, "fontWeight": 700,
   "fills": [{"r": 0.1, "g": 0.1, "b": 0.1}]}
]
```

**Update existing nodes** (using nodeId from previous job's tempIdMap):
```json
[
  {"op": "UPDATE_NODE", "tempId": "u1", "nodeId": "17:65",
   "fills": [{"r": 1, "g": 0, "b": 0}], "opacity": 0.8},

  {"op": "UPDATE_NODE", "tempId": "u2", "nodeId": "17:66",
   "text": "Updated heading", "fontSize": 32, "fontWeight": 700}
]
```

**Delete nodes:**
```json
[
  {"op": "DELETE_NODE", "tempId": "d1", "nodeId": "17:65"}
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

**All create ops:** `tempId`, `parentTempId`, `parentNodeId`, `name`, `x`, `y`, `fills [{r,g,b,a}]`, `stroke {r,g,b,a,weight,align}`, `opacity`

**CREATE_FRAME:** `w`, `h`, `cornerRadius`, `layoutMode`, `itemSpacing`, `paddingLeft/Right/Top/Bottom`, `primaryAxisAlignItems`, `counterAxisAlignItems`, `clipsContent`, `dropShadow {color{r,g,b,a}, offset{x,y}, radius}`

**CREATE_RECTANGLE:** `w`, `h`, `cornerRadius`

**CREATE_ELLIPSE:** `w`, `h`

**CREATE_TEXT:** `text`, `fontSize`, `fontFamily`, `fontWeight`, `textAlignHorizontal`, `textAutoResize`, `w`, `h`, `lineHeight`, `letterSpacing`

**UPDATE_NODE:** `nodeId` (required), plus any property to change: `name`, `x`, `y`, `w`, `h`, `fills`, `stroke`, `opacity`, `cornerRadius`, `text`, `fontSize`, `fontFamily`, `fontWeight`, `visible`

**DELETE_NODE:** `nodeId` (required)

### read_node_tree Response

The tree now includes rich property data for each node:
- `id`, `name`, `type`, `x`, `y`, `width`, `height`
- `fill` — first solid fill color `{r, g, b, a}`
- `opacity` — if not 1
- `cornerRadius` — if > 0
- `text`, `fontSize`, `fontFamily`, `fontWeight` — for text nodes
- `layoutMode`, `itemSpacing` — for auto-layout frames
- `visible` — if hidden
